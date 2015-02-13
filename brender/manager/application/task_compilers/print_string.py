import json
import logging

from application import app

class task_compiler():
    @staticmethod
    def compile(worker, task):

    	settings=json.loads(task['settings'])

    	task_command = [ 'echo',
    		settings['text'],
    	]

    	return task_command