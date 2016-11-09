/**
 * Removes the task from the task list and shot list, and show the 'task-add-link'
 * when this was the last task in its category.
 */
function _remove_task_from_list(task_id) {
    var $task_link = $('#task-' + task_id)
    var $task_link_parent = $task_link.parent();
    $task_link.hideAndRemove(300, function() {
        if ($task_link_parent.children('.task-link').length == 0) {
            $task_link_parent.find('.task-add-link').removeClass('hidden');
        }
    });
}

/**
 * Open an item such as tasks/shots in the #item-details div
 */
function item_open(item_id, item_type, pushState, project_url)
{
    if (item_id === undefined || item_type === undefined) {
        throw new ReferenceError("item_open(" + item_id + ", " + item_type + ") called.");
    }

    if (typeof project_url === 'undefined') {
        project_url = ProjectUtils.projectUrl();
        if (typeof project_url === 'undefined') {
            throw new ReferenceError("ProjectUtils.projectUrl() undefined");
        }
    }

    $('#col_right .col_header span.header_text').text(item_type + ' details');

    // Style elements starting with item_type and dash, e.g. "#shot-uuid"
    $('[id^="' + item_type + '-"]').removeClass('active');
    $('#' + item_type + '-' + item_id).addClass('active');

    // Special case to highlight the shot row when opening task in shot context
    if (ProjectUtils.context() == 'shot' && item_type == 'task'){
        $('[id^="shot-"]').removeClass('active');
        $('#task-' + item_id).closest('.table-row').addClass('active');
    }

    var item_url = '/flamenco/' + project_url + '/' + item_type + 's/' + item_id;
    var push_url = item_url;
    if (ProjectUtils.context() == 'shot' && item_type == 'task'){
        push_url = '/flamenco/' + project_url + '/shots/with-task/' + item_id;
    }
    item_url += '?context=' + ProjectUtils.context();

    statusBarSet('default', 'Loading ' + item_type + '…');

    $.get(item_url, function(item_data) {
        statusBarClear();
        $('#item-details').html(item_data);
    }).fail(function(xhr) {
        if (console) {
            console.log('Error fetching task', item_id, 'from', item_url);
            console.log('XHR:', xhr);
        }

        statusBarSet('error', 'Failed to open ' + item_type, 'pi-warning');

        if (xhr.status) {
            $('#item-details').html(xhr.responseText);
        } else {
            $('#item-details').html('<p class="text-danger">Opening ' + item_type + ' failed. There possibly was ' +
            'an error connecting to the server. Please check your network connection and ' +
            'try again.</p>');
        }
    });

    // Determine whether we should push the new state or not.
    pushState = (typeof pushState !== 'undefined') ? pushState : true;
    if (!pushState) return;

    // Push the correct URL onto the history.
    var push_state = {itemId: item_id, itemType: item_type};

    window.history.pushState(
            push_state,
            item_type + ': ' + item_id,
            push_url
    );
}

// Fine if project_url is undefined, but that requires ProjectUtils.projectUrl().
function task_open(task_id, project_url)
{
    item_open(task_id, 'task', true, project_url);
}

function shot_open(shot_id)
{
    item_open(shot_id, 'shot');
}

window.onpopstate = function(event)
{
    var state = event.state;

    item_open(state.itemId, state.itemType, false);
}

/**
 * Create a task and show it in the #item-details div.
 * NOTE: Not used at the moment, we're creating shots via Blender's VSE
 */
function shot_create(project_url)
{
    if (project_url === undefined) {
        throw new ReferenceError("shot_create(" + project_url+ ") called.");
    }
    var url = '/flamenco/' + project_url + '/shots/create';

    data = {
        project_url: project_url
    };

    $.post(url, data, function(shot_data) {
        shot_open(shot_data.shot_id);
    })
    .fail(function(xhr) {
        if (console) {
            console.log('Error creating task');
            console.log('XHR:', xhr);
        }
        $('#item-details').html(xhr.responseText);
    });
}

/**
 * Adds the task item to the shots/tasks list.
 *
 * 'shot_id' can be undefined if the task isn't attached to a shot.
 */
function task_add(shot_id, task_id, task_type)
{
    if (task_id === undefined || task_type === undefined) {
        throw new ReferenceError("task_add(" + shot_id + ", " + task_id + ", " + task_type + ") called.");
    }

    var project_url = ProjectUtils.projectUrl();
    var url = '/flamenco/' + project_url + '/tasks/' + task_id;
    var context = ProjectUtils.context();

    if (context == 'task') {
        /* WARNING: This is a copy of an element of flamenco/tasks/for_project #task-list.col-list
         * If that changes, change this too. */
        $('#task-list').append('\
            <a class="col-list-item task-list-item status-todo task-link active"\
                href="' + url + '"\
                data-task-id="' + task_id + '"\
                id="task-' + task_id + '">\
                <span class="status-indicator"></span>\
                <span class="name">-save your task first-</span>\
                <span class="type">-</span>\
            </a>\
            ');
    } else if (context == 'shot') {
        if (shot_id === undefined) {
            throw new ReferenceError("task_add(" + shot_id + ", " + task_id + ", " + task_type + ") called in shot context.");
        }

        var $shot_cell = $('#shot-' + shot_id + ' .table-cell.task-type.' + task_type);
        var url = '/flamenco/' + project_url + '/shots/with-task/' + task_id;

        /* WARNING: This is a copy of an element of flamenco/shots/for_project #task-list.col-list
         * If that changes, change this too. */
        $shot_cell.append('\
            <a class="status-todo task-link active"\
                title="-save your task first-"\
                href="' + url + '"\
                data-task-id="' + task_id + '"\
                id="task-' + task_id + '">\
            </a>\
        ');

        $shot_cell.find('.task-add.task-add-link').addClass('hidden');
    }
}

/**
 * Create a task and show it in the #item-details div.
 *
 * 'shot_id' may be undefined, in which case the task will not
 * be attached to a shot.
 */
function task_create(shot_id, task_type)
{
    if (task_type === undefined) {
        throw new ReferenceError("task_create(" + shot_id + ", " + task_type + ") called.");
    }

    var project_url = ProjectUtils.projectUrl();
    var url = '/flamenco/' + project_url + '/tasks/create';
    var has_shot_id = typeof shot_id !== 'undefined';

    data = {
        task_type: task_type,
    };
    if (has_shot_id) data.parent = shot_id;

    $.post(url, data, function(task_data) {
        if (console) console.log('Task created:', task_data);
        task_open(task_data.task_id);
        task_add(shot_id, task_data.task_id, task_type);
    })
    .fail(function(xhr) {
        if (console) {
            console.log('Error creating task');
            console.log('XHR:', xhr);
        }
        $('#item-details').html(xhr.responseText);
    })
    .done(function(){
        $('#item-details input[name="name"]').focus();
    });
}

function flamenco_form_save(form_id, item_id, item_save_url, options)
{
    // Mandatory option.
    if (typeof options === 'undefined' || typeof options.type === 'undefined') {
        throw new ReferenceError('flamenco_form_save(): options.type is mandatory.');
    }

    var $form = $('#' + form_id);
    var $button = $form.find("button[type='submit']");

    var payload = $form.serialize();
    var $item = $('#' + item_id);

    $button.attr('disabled', true);
    $item.addClass('processing');

    statusBarSet('', 'Saving ' + options.type + '…');

    if (console) console.log('Sending:', payload);

    $.post(item_save_url, payload)
        .done(function(saved_item) {
            if (console) console.log('Done saving', saved_item);

            statusBarSet('success', 'Saved ' + options.type + '. ' + saved_item._updated, 'pi-check');

            $form.find("input[name='_etag']").val(saved_item._etag);

            if (options.done) options.done($item, saved_item);
        })
        .fail(function(xhr_or_response_data) {
            // jQuery sends the response data (if JSON), or an XHR object (if not JSON).
            if (console) console.log('Failed saving', options.type, xhr_or_response_data);

            $button.removeClass('btn-default').addClass('btn-danger');

            statusBarSet('error', 'Failed saving. ' + xhr_or_response_data.status, 'pi-warning');

            if (options.fail) options.fail($item, xhr_or_response_data);
        })
        .always(function() {
            $button.attr('disabled', false);
            $item.removeClass('processing');

            if (options.always) options.always($item);
        })
    ;

    return false; // prevent synchronous POST to current page.
}

function task_save(task_id, task_url) {
    return flamenco_form_save('task_form', 'task-' + task_id, task_url, {
        done: function($task, saved_task) {
            // Update the task list.
            // NOTE: this is tightly linked to the HTML of the task list in for_project.jade.
            $('.task-name-' + saved_task._id).text(saved_task.name).flashOnce();
            $task.find('span.name').text(saved_task.name);
            $task.find('span.type').text(saved_task.properties.task_type);
            $task.find('span.status').text(saved_task.properties.status.replace('_', ' '));

            $task
                .removeClassPrefix('status-')
                .addClass('status-' + saved_task.properties.status)
                .flashOnce()
            ;

            task_open(task_id);
        },
        fail: function($item, xhr_or_response_data) {
            if (xhr_or_response_data.status == 412) {
                // TODO: implement something nice here. Just make sure we don't throw
                // away the user's edits. It's up to the user to handle this.
            } else {
                $('#item-details').html(xhr_or_response_data.responseText);
            }
        },
        type: 'task'
    });
}

function shot_save(shot_id, shot_url) {
    return flamenco_form_save('shot_form', 'shot-' + shot_id, shot_url, {
        done: function($shot, saved_shot) {
            // Update the shot list.
            $('.shot-name-' + saved_shot._id).text(saved_shot.name);
            $shot
                .removeClassPrefix('status-')
                .addClass('status-' + saved_shot.properties.status)
                .flashOnce()
            ;
            shot_open(shot_id);
        },
        fail: function($item, xhr_or_response_data) {
            if (xhr_or_response_data.status == 412) {
                // TODO: implement something nice here. Just make sure we don't throw
                // away the user's edits. It's up to the user to handle this.
            } else {
                $('#item-details').html(xhr_or_response_data.responseText);
            }
        },
        type: 'shot'
    });
}

function task_delete(task_id, task_etag, task_delete_url) {
    if (task_id === undefined || task_etag === undefined || task_delete_url === undefined) {
        throw new ReferenceError("task_delete(" + task_id + ", " + task_etag + ", " + task_delete_url + ") called.");
    }

    $('#task-' + task_id).addClass('processing');

    $.ajax({
        type: 'DELETE',
        url: task_delete_url,
        data: {'etag': task_etag}
    })
    .done(function(e) {
        if (console) console.log('Task', task_id, 'was deleted.');
        $('#item-details').fadeOutAndClear();
        _remove_task_from_list(task_id);

        statusBarSet('success', 'Task deleted successfully', 'pi-check');
    })
    .fail(function(xhr) {

        statusBarSet('error', 'Unable to delete task, code ' + xhr.status, 'pi-warning');

        if (xhr.status == 412) {
            alert('Someone else edited this task before you deleted it; refresh to try again.');
            // TODO: implement something nice here. Just make sure we don't throw
            // away the user's edits. It's up to the user to handle this.
            // TODO: refresh activity feed and point user to it.
        } else {
            // TODO: find a better place to put this error message, without overwriting the
            // task the user is looking at in-place.
            $('#task-view-feed').html(xhr.responseText);
        }
    });
}

function loadActivities(url)
{
    return $.get(url)
	.done(function(data) {
		if(console) console.log('Activities loaded OK');
		$('#activities').html(data);
	})
	.fail(function(xhr) {
	    if (console) {
	        console.log('Error fetching activities');
	        console.log('XHR:', xhr);
	    }

        statusBarSet('error', 'Opening activity log failed.', 'pi-warning');

	    if (xhr.status) {
	        $('#activities').html(xhr.responseText);
	    } else {
	        $('#activities').html('<p class="text-danger">Opening activity log failed. There possibly was ' +
	        'an error connecting to the server. Please check your network connection and ' +
	        'try again.</p>');
	    }
	});
}

$(function() {
    $("a.shot-link[data-shot-id]").click(function(e) {
        e.preventDefault();
        // delegateTarget is the thing the event hander was attached to,
        // rather than the thing we clicked on.
        var shot_id = e.delegateTarget.dataset.shotId;
        shot_open(shot_id);
    });

    $("a.task-link[data-task-id]").click(function(e) {
        e.preventDefault();
        var task_id = e.delegateTarget.dataset.taskId;
        var project_url = e.delegateTarget.dataset.projectUrl;  // fine if undefined
        task_open(task_id, project_url);
    });
});

$(document).on('keyup', function(e){
    if (ProjectUtils.context() == 'shot' || ProjectUtils.context() == 'task'){

        // Save on Ctrl + Enter anytime except when comments is on focus
        if ($('#comment_field') && $('#comment_field').not(':focus')){
            if ((e.keyCode == 10 || e.keyCode == 13) && e.ctrlKey){
                $("#item-save").trigger( "click" );
            }
        }
    }
});
