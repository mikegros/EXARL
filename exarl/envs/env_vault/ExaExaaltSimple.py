# This material was prepared as an account of work sponsored by an agency of the
# United States Government.  Neither the United States Government nor the United
# States Department of Energy, nor Battelle, nor any of their employees, nor any
# jurisdiction or organization that has cooperated in the development of these
# materials, makes any warranty, express or implied, or assumes any legal
# liability or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights. Reference
# herein to any specific commercial product, process, or service by trade name,
# trademark, manufacturer, or otherwise does not necessarily constitute or imply
# its endorsement, recommendation, or favoring by the United States Government
# or any agency thereof, or Battelle Memorial Institute. The views and opinions
# of authors expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#                 PACIFIC NORTHWEST NATIONAL LABORATORY
#                            operated by
#                             BATTELLE
#                             for the
#                   UNITED STATES DEPARTMENT OF ENERGY
#                    under Contract DE-AC05-76RL01830

import numpy  as np
import gym

NAME = str(np.random.randint(99999)) + str(np.random.randint(99999))

def dirichlet_draw(alphas):
    sample = [np.random.gamma(a, 1) for a in alphas]
    sums   = sum(sample)
    sample = [x/sums for x in sample]
    return sample

def get_graph_dist(knownStates, state):
    all_keys   = knownStates.keys()
    graph_dist = {}
    for loop_state in all_keys:
        graph_dist[loop_state] = 5
    graph_keys = [[state]]
    inc_keys   = [state]
    for ii in range(5):
        new_keys = []
        for key in graph_keys[ii]:
            graph_dist[key] = ii
            tmp_keys = [x for x in knownStates[key].probs.keys() if x not in inc_keys]
            tmp_keys += [x for x in knownStates.keys() if (key in knownStates[x].probs.keys()) and (x not in tmp_keys)]
            inc_keys += tmp_keys
            new_keys += tmp_keys
        graph_keys.append(new_keys)
            
    return graph_dist


def VE(traj, knownStates, database, nWorkers, d_prior):
    print('running VE... '+str(len(knownStates.keys()))+' states discovered')
    builds={}
    for a in knownStates.keys():
        builds[a]=0

    taskList=[]
    for _ in range(nWorkers):
        virtuallyConsumed={}
        for i in knownStates.keys():
            virtuallyConsumed[i]=0

        state=traj[-1]
        while(len(database[state])+builds[state]>virtuallyConsumed[state]):
            virtuallyConsumed[state]+=1
            #print(database[state])
            try:
                state=database[state][virtuallyConsumed[state]-1]
                #print('virtual consumed to state ',state)
            except:
                # offset      = np.array([20., 0., 0., 0., 0., 0.])
                offset      = np.array([0., 0., 0., 0., 0., 0.])
                prior_p     = d_prior[0] + offset + 1.e-1
                graph_dist  = get_graph_dist(knownStates, state)
                d_alpha     = np.array([ prior_p[graph_dist[key]] for key in knownStates.keys() ])
                # print("dalpha: ", d_alpha)
                # print("KNOWN STATES: ", knownStates.keys(), d_alpha)
                # print(graph_dist)
                # print("Dist 1:", knownStates[state].probs.keys())
                # print(d_prior)
                count_num = np.array([knownStates[state].counts[x] if x in knownStates[state].counts.keys() else 0 for x in knownStates.keys()])
                if len(count_num) == 1:
                    sample_p = [1.]
                else:
                    #print("count: ", count_num)
                    #print("d_alpha: ", d_alpha)
                    # sample_p   = np.random.dirichlet(count_num+d_alpha)
                    sample_p   = dirichlet_draw(count_num + d_alpha)
                    #print("sample_p: ", sample_p)
                # print(count_num)
                # print(sample_p)
                try:
                    state      = np.random.choice(list(knownStates.keys()),p=sample_p)
                except:
                    print("Samp_p: ", sample_p)
                    print("counts: ", count_num)
                    print("d_alpha: ", d_alpha)
                    print("PRIOR P: ",prior_p)
                    print("d_prior: ",d_prior)
                    print("d_prior0: ",d_prior[0])
                    state      = np.random.choice(list(knownStates.keys()),p=sample_p)
                # print("STATE: ",state)
                # print("KNOWNSTATE KEYS: ", knownStates[state].probs.keys())
                # print("====================")
                #print('VE SAMPLE FOR PENDING SEGMENT ->',state)
        #print('scheduling in state ',state)
        taskList.append(state)
        builds[state]+=1
    return taskList

class StateStatistics:
    #constructor to initialize StateStatistic object
    def __init__(self, label, Map):
        self.Map    = Map
        self.counts = {}
        for neigh in self.Map[int(label)].keys():
            self.counts[neigh]=0
        #print('state '+str(label)+' will connect to: '+str(self.counts.keys()))
        self.nSegments=0
        self.nTransitions=0
        self.label = int(label)
        self.probs={}
        self.l=0
        self.lp=0
        self.initP=-1

    #clear old probabilities
    def clearProbs(self):
        self.probs={}

    #update state statistics
    def update(self, finalState):
        self.nSegments+=1
        try:
                self.counts[finalState]+=1
        except:
                self.counts[finalState]=1
        if(finalState!=self.label):
                self.nTransitions+=1


class ExaExaaltSimple(gym.Env):
    def __init__(self,**kwargs):
        super().__init__()
        """

        """
        stateDepth       = 50 #segments
        number_of_states = 100000

        self.n_states  = number_of_states
        self.nWorkers  = 500
        self.num_done  = 0
        self.WCT       = 0
        self.RUN_TIME  = 100 #10000
        
        self.database    = {}
        self.knownStates = {}
        self.selfTrans   = []
        self.selfTrans.append(StateStatistics(0, [{0:0,1:1}]))
        self.traj        = []

        self.state_order = [ii for ii in range(self.n_states)]

        self.Map={}
        side= 100
        for i in range(number_of_states):
            self.Map[i]={}
            self.Map[i][i]=1-1.0/stateDepth
        
            R=(1-self.Map[i][i])/4
            if(i%side==0):
                #left side
                self.Map[i][(i-1+side)%number_of_states]=R
                self.Map[i][(i+1)%number_of_states]=R
            else:
                if(i%side==(side-1)):
                    #right side
                    self.Map[i][i-1]=R
                    self.Map[i][(i+1-side)%number_of_states]=R
        
                else:
                    #not an edge
                    self.Map[i][i-1]=R
                    self.Map[i][(i+1)%number_of_states]=R
        
            self.Map[i][(i-side)%number_of_states]=R
            self.Map[i][(i+side)%number_of_states]=R


        self.INITIAL_STATE              = int((side/2)*side+side/2)    
        self.knownStates[self.INITIAL_STATE] = StateStatistics(self.INITIAL_STATE, self.Map) 
        self.database[self.INITIAL_STATE]    = []
        self.traj.append(self.INITIAL_STATE)                                               


        # Set bounds using the structure in the Cartpole example
        # high = np.repeat(np.finfo(np.float32).max, self.n_obs)

        # self.action_space      = gym.spaces.Box(np.zeros(self.n_states), np.ones(self.n_states))
        # self.observation_space = gym.spaces.Box(np.zeros(self.n_states), np.ones(self.n_states))

        self.action_space      = gym.spaces.Box(np.zeros(2), np.array([100.,100.]))
        self.observation_space = gym.spaces.Box(low=np.array([0., 0.]),high=np.array([1., 1.]))

    def crankModel(self):
        l={}
        pi={}
        for k in self.knownStates.keys():
            l[k]=0
            pi[k]=1
        for i in self.knownStates.keys():
            for j in self.Map[i].keys():
                if(j in self.knownStates.keys()):
                    l[i]+=0.5*(self.knownStates[i].counts[j]+self.knownStates[j].counts[i])
    
        iterations=0
        while(True):
            iterations+=1
            nextl={}
            for k in self.knownStates.keys():
                    nextl[k]=0
            for i in self.knownStates.keys():
                for j in self.Map[i].keys():
                    if(j in self.knownStates.keys()):
                        if(self.knownStates[i].counts[j]+self.knownStates[j].counts[i]>0):
                            nextl[i]+=((self.knownStates[i].counts[j]+self.knownStates[j].counts[i])*l[i]*pi[j])/(l[j]*pi[i]+l[i]*pi[j])
            #check accuracy
            accuracy=0
            for i in self.knownStates.keys():
                    accuracy+=np.abs(l[i]-nextl[i])
            if(accuracy<1e-7 or iterations>9):
                #print (accuracy)
                #transfer lambdas
                for i in self.knownStates.keys():
                    l[i]=nextl[i]
                break
            else:
                #print (accuracy)
                #transfer lambdas
                for i in self.knownStates.keys():
                    l[i]=nextl[i]
    
        for i in self.knownStates.keys():
            self.knownStates[i].clearProbs()
            for j in self.knownStates[i].counts.keys():
                if(j in list(self.knownStates.keys())):
                    if(self.knownStates[i].counts[j]+self.knownStates[j].counts[i]>0 and i!=j):
                        self.knownStates[i].probs[j]=((self.knownStates[i].counts[j]+self.knownStates[j].counts[i])*pi[j])/(l[j]*pi[i]+l[i]*pi[j])
            if(sum(self.knownStates[i].probs.values())<1):
                self.knownStates[i].probs[i]=1-sum(self.knownStates[i].probs.values())
            if(sum(self.knownStates[i].probs.values())>1):
                norm=sum(self.knownStates[i].probs.values())
                for key in self.knownStates[i].probs.keys():
                    self.knownStates[i].probs[key]=self.knownStates[i].probs[key]/norm
            """
            for neighborState in self.knownStates[i].counts.keys():
                try:
                    print('probs ',self.knownStates[i].label,'->',neighborState,self.knownStates[i].probs[neighborState])
                except:
                    0
            """

    def schedule(self, WCT):
        self.crankModel()
        taskList=VE(self.traj, self.knownStates, self.database, self.nWorkers)
        for i in range(self.nWorkers):
            workerID=i
            buildState=taskList[i]
            endState=np.random.choice(list(self.Map[buildState].keys()),p=list(self.Map[buildState].values()))
            self.knownStates[buildState].update(endState)
            self.database[buildState].append(endState)
            if(endState not in self.knownStates.keys()):
                self.knownStates[endState]=StateStatistics(endState,self.Map)
                self.database[endState]=[]
            #print(WCT,workerID,buildState,endState)
            # with open("traceOutput_2dModel"+str(NAME), "a") as myfile:
            #     myfile.write(
            #                 str(round(WCT,3))+' '+
            #                 str(workerID)+' '+
            #                 str(buildState)+' '+
            #                 str(endState)+' '+
            #                 '\n')
        pass

    def step(self, action):
        done = False
        # launchStates = np.random.choice(range(self.n_states), size=self.nWorkers)#, p=action)
        self.crankModel()
        #print("Action: ",action)
        taskList = [1]# VE(self.traj, self.knownStates, self.database, self.nWorkers, action)
        # for i in range(1):# self.nWorkers):
        #     workerID   = i
        #     buildState = taskList[i] # launchStates[i]
        #     endState   = np.random.choice(list(self.Map[buildState].keys()),p=list(self.Map[buildState].values()))

        #     self.knownStates[buildState].update(endState)
        #     if buildState == endState:
        #         self.selfTrans[0].update(0)
        #     else:
        #         self.selfTrans[0].update(1)
        #     self.database[buildState].append(endState)
        #     if (endState not in self.knownStates.keys()):
        #         self.knownStates[endState]=StateStatistics(endState, self.Map)
        #         self.database[endState] = []
        #     # with open("traceOutput_2dModel"+str(NAME), "a") as myfile:
        #     #     myfile.write(
        #     #             str(round(self.WCT, 3)) + " "+
        #     #             str(workerID) + " " +
        #     #             str(buildState) + " " +
        #     #             str(endState) +" " +
        #     #             '\n')

        self.WCT+=1
        # while(True):
        #     current_state=self.traj[-1]
        #     try:
        #         next_state=self.database[current_state].pop(0)
        #         self.traj.append(next_state)
        #     except:
        #         with open("BayesRL_dataOutput_2dModel_"+str(NAME), "a") as myfile:
        #                 myfile.write(
        #                 str(round(self.WCT,3))+' '+
        #                 str(len(self.traj))+' '+
        #                 str(self.WCT*self.nWorkers)+' '+
        #                 str(len(self.traj)/float(self.WCT*self.nWorkers))+' '+
        #                 '\n')
        #         break

        if (self.WCT >= self.RUN_TIME):
            done = True

        """ Iterates the testing process forward one step """

        # reward        = len(self.traj)/float(self.WCT*self.nWorkers) # - np.sum(action)/1000.
        reward = action[0] # - action[1]
        current_state = self.traj[-1]

        next_state = self.generate_data()
       
        info = None
        # print("Action, Rewards, Done: ",action, reward, " ", done)
        return next_state, reward, done, info

    def reset(self):
        """ Start environment over """
        side = 100

        self.WCT                             = 0 
        self.INITIAL_STATE                   = int((side/2)*side+side/2)
        self.traj                            = []
        self.database                        = {}
        self.selfTrans                       = []
        self.selfTrans.append(StateStatistics(0, [{0:0,1:1}]))
        self.knownStates                     = {}
        self.knownStates[self.INITIAL_STATE] = StateStatistics(self.INITIAL_STATE, self.Map)
        self.database[self.INITIAL_STATE]    = []
        self.traj.append(self.INITIAL_STATE)

        return self.generate_data() # Return new state

    def render(self):
        """ Not relevant here but left for template convenience """
        return 0

    def generate_data(self):
        prob_dist    = np.zeros(self.n_states)
        curr_state   = self.traj[-1]
        total_counts = 0
        out_counts   = 0
        for j in self.knownStates[curr_state].counts.keys():
            if(j in list(self.knownStates.keys())):
                if(curr_state!=j):
                    total_counts += self.knownStates[curr_state].counts[j]+self.knownStates[j].counts[curr_state]
                    out_counts   += self.knownStates[curr_state].counts[j]+self.knownStates[j].counts[curr_state]
                else:
                    total_counts += self.knownStates[curr_state].counts[j]+self.knownStates[j].counts[curr_state]
        next_state = np.array([total_counts, out_counts]) 
        # print(list(self.Map[curr_state].values()))
        # print(list(self.Map[curr_state].keys()))
        # print(list(self.Map.keys()))
        # print(list(self.knownStates.keys()))
        # prob_dist[self.Map[curr_state].keys()] = 1. * np.array(list(self.Map[curr_state].values()))

        # for ii in range(5):
        #     t_mat = np.zeros(self.n_states, self.n_states)
        #     for jj in np.where(prob_dist > 0.)[0]:
        #         t_mat[jj,self.Map[jj].keys()] = list(self.Map[jj].values())
        #     prob_dist = t_mat @ prob_dist

        # self.state_order = np.argsort(prob_dist)[::-1]
        # next_state       = prob_dist[self.state_order]
        return np.ones_like(next_state)
