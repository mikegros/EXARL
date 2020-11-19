from .registration import register, make

register(
	id = 'sync',
	entry_point = 'workflows.workflow_vault:SYNC'
)

register(
	id = 'async',
	entry_point = 'workflows.workflow_vault:ASYNC'
)

register(
		id = 'seed',
		entry_point = 'workflows.workflow_vault:SEED'
)

