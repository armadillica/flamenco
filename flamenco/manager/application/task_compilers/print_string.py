import json


class task_compiler():
    @staticmethod
    def compile(worker, task, add_file):

        settings = json.loads(task['settings'])

        task_command = ['echo',
                        settings['text'],
                        ]

        return task_command
