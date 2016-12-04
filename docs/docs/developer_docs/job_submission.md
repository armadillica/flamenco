
# Job submission

The Manager collection on Flamenco Server will store all manager configuration. This will be queried by manager on demand.


```
{
	'job_types': {
		'blender_resumable_render':{
			'commands': {
				'blender' : {
					'linux': '/dalai/blender',
				}
			},
			'paths' {
				'shared': {
					'linux': '/shared',
					'osx': '/Volumes/shared',
				}
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