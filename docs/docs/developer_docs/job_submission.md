
# Job submission

The Manager collection on Flamenco Server will store all manager configuration. This will be queried by manager on demand.

```
{
	'job_types': [
		{
			'name': 'blender_resumable_render',
			'vars': [
				{
					'name': 'blender',
					'linux': '/shared/software/blender',
					'darwin': '/Volumes/shared/software/blender',
				},
				{
					'name': 'render',
					'linux': '/render',
					'darwin': '/Volumes/render',
				}
			],
			'settings_schema': {
				'frames': {
					'type': 'string',
					# '1-20,21,25-30'
				},
				'chunk_size': {
					'type': 'integer',
					# 5
				},
				'filepath': {
					'type': 'string',
					# '/shared/shot1.blend'
				},
				'render_output': {
					'type': 'string',
					# '{render}/shot1/'
				}
			}
		}
	]
}
```

In the future, the model will evolve to the following:

```
{
	'job_types': {
		'blender_resumable_render':{
			'blender': {
				'linux': '/shared/software/blender',
				'darwin': '/Volumes/shared/software/blender',
			},
			'render': {
				'linux': '/render',
				'darwin': '/Volumes/render',
			}
		}
	}
}
```


This allows us to provide extra info about a job, once we create it via the client (Blender Cloud add-on).

Example:

- user submits `blender_resumable_render` via add-on
- server creates job and tasks, and returns job `_id` and manager settings for that job_type (e.g., `paths`)
- add-on checks that `paths` exists
- add-on bam packs files combining `paths` and `_id` as output for the packing
- add-on sets the job as `queued`
 

Blender Cloud add-on expands to support Flamenco (same auth, no extra user prefs).