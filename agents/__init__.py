from .registration import register, make

register(
	id='DQN-v0',
	entry_point='agents.agent_vault:DQN',
)
register(
	id='DQN-LSTM-v0',
	entry_point='agents.agent_vault:DQN_LSTM',
)
