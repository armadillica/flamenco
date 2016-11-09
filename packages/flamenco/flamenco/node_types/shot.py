node_type_shot = {
    'name': 'flamenco_shot',
    'description': 'Shot Node Type, for shots',
    'dyn_schema': {
        # How many frames are trimmed from the start of the shot in the edit.
        'trim_start_in_frames': {
            'type': 'integer',
        },
        # Duration (of the visible part) of the shot in the edit.
        'duration_in_edit_in_frames': {
            'type': 'integer',
        },
        # Cut-in time of the shot in the edit (i.e. frame number where it starts to be visible).
        'cut_in_timeline_in_frames': {
            'type': 'integer',
        },
        'status': {
            'type': 'string',
            'allowed': [
                'on_hold',
                'todo',
                'in_progress',
                'review',
                'final'
            ],
            'default': 'todo',
            'required_after_creation': True,
        },
        'notes': {
            'type': 'string',
            'maxlength': 256,
        },
        'used_in_edit': {
            'type': 'boolean',
            'default': True,
        },
    },
    'form_schema': {},
    'parent': ['scene']
}

task_types = ['layout', 'animation', 'lighting', 'fx', 'rendering']

human_readable_properties = {
    'properties.trim_start_in_frames': 'Trim Start',
    'properties.duration_in_edit_in_frames': 'Duration in Edit',
    'properties.cut_in_timeline_in_frames': 'Cut-in',
}
