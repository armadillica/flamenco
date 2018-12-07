/**
 * Open an item such as tasks/jobs in the corresponding div
 * Jobs load on #item-details, Tasks load on #col_main-overlay-content
 */
function item_open(item_id, item_type, pushState, project_url)
{
    if (item_id === undefined || item_type === undefined) {
        throw new ReferenceError("item_open(" + item_id + ", " + item_type + ") called.");
    }

    var is_task_or_job = (item_type == 'task' || item_type == 'job');
    if (is_task_or_job && typeof project_url === 'undefined') {
        project_url = ProjectUtils.projectUrl();
        if (typeof project_url === 'undefined') {
            throw new ReferenceError("ProjectUtils.projectUrl() undefined");
        }
    }

    // Style elements starting with item_type and dash, e.g. "#job-uuid"
    var clean_classes = 'active processing';
    var current_item = $('#' + item_type + '-' + item_id);

    $('[id^="' + item_type + '-"]').removeClass(clean_classes);
    current_item
        .removeClass(clean_classes)
        .addClass('processing');

    var item_url;
    var push_url;

    switch(item_type) {
        case 'task':
        case 'job':
            var type_for_url = item_type + 's';
            if (item_type == 'job' && ProjectUtils.context() == 'archive')
                type_for_url = 'archive'
            item_url = '/flamenco/' + project_url + '/' + type_for_url + '/' + item_id;
            if (ProjectUtils.context() == 'job' && item_type == 'task'){
                push_url = '/flamenco/' + project_url + '/jobs/with-task/' + item_id;
            }
            break;
        case 'manager':
            item_url = '/flamenco/managers/' + item_id;
            break;
    }
    if (typeof push_url == 'undefined') push_url = item_url;
    item_url += '?context=' + ProjectUtils.context();

    statusBarSet('default', 'Loading ' + item_type + '…');

    $.get(item_url, function(item_data) {
        statusBarClear();

        if (ProjectUtils.context() == 'job' && item_type == 'task'){
            $('#col_main-overlay-content').html(item_data);
            $('#col_main-overlay .col_header span.header_text').text(item_type + ' details');
            $('#col_main-overlay').addClass('active');
        } else {
            $('#item-details').html(item_data);
            $('#col_right .col_header span.header_text').text(item_type + ' details');
        }

        current_item
            .removeClass(clean_classes)
            .addClass('active');

    }).fail(function(xhr) {
        if (console) {
            console.log('Error fetching task', item_id, 'from', item_url);
            console.log('XHR:', xhr);
        }

        current_item.removeClass(clean_classes);
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
function job_open(job_id, project_url)
{
    item_open(job_id, 'job', true, project_url);
}
function task_open(task_id, project_url)
{
    item_open(task_id, 'task', true, project_url);
}
function manager_open(manager_id)
{
    item_open(manager_id, 'manager', true);
}


window.onpopstate = function(event)
{
    var state = event.state;
    if (state == null) {
        // We're going back to the first time this page was opened, which
        // means we should show the first Job/Task/Manager.
        ctx = ProjectUtils.context();
        state = {
            itemId: $('.item-list a[data-' + ctx + '-id]').first().data(ctx + '-id'),
            itemType: ctx,
        }
    }
    item_open(state.itemId, state.itemType, false);
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

function loadTasks(url) {
    return $.get(url)
    .done(function(data) {
        if(console) console.log('Tasks loaded OK\n' + url);
        $('#tasks').html(data);
        setupJsTaskLinkClickHandlers();

        // Mark the showing task as 'active' in the task list.
        var task_id = document.body.dataset.taskId;
        if (typeof task_id != 'undefined') {
            $('#task-' + task_id).addClass('active');
        }
    })
}

function setupJsTaskLinkClickHandlers() {
    $("a.task-link[data-task-id]")
    .off('click')  // clean up previous click handlers, before adding another one.
    .click(function(e) {
        e.preventDefault();
        var task_id = e.delegateTarget.dataset.taskId;
        var project_url = e.delegateTarget.dataset.projectUrl;  // fine if undefined
        task_open(task_id, project_url);
    });
}

function setupJsJobLinkClickHandlers() {
    $("a.job-link[data-job-id]")
    .off('click')  // clean up previous click handlers, before adding another one.
    .click(function(e) {
        e.preventDefault();
        // delegateTarget is the thing the event hander was attached to,
        // rather than the thing we clicked on.
        var job_id = e.delegateTarget.dataset.jobId;
        job_open(job_id);
    });
}

function setupJsManagerLinkClickHandlers() {
    $("a.manager-link[data-manager-id]")
    .off('click')  // clean up previous click handlers, before adding another one.
    .click(function(e) {
        e.preventDefault();
        // delegateTarget is the thing the event hander was attached to,
        // rather than the thing we clicked on.
        var manager_id = e.delegateTarget.dataset.managerId;
        manager_open(manager_id);
    });
}

$(function() {
    setupJsJobLinkClickHandlers();
    setupJsTaskLinkClickHandlers();
    setupJsManagerLinkClickHandlers();
});

/**
 * Request cancellation or re-queueing of the given job ID.
 */
function setJobStatus(job_id, new_status) {
    if (typeof job_id === 'undefined' || typeof new_status === 'undefined') {
        if (console) console.log("setJobStatus(" + job_id + ", " + new_status + ") called");
        return;
    }

    return $.post('/flamenco/jobs/' + job_id + '/set-status', {status: new_status})
    .done(function(data) {
        if(console) console.log('Job set-status request OK');
        // Reload the entire page, since both the view-embed and the job list need refreshing.
        location.reload(true);
    })
    .fail(function(xhr) {
        if (console) {
            console.log('Error setting job status');
            console.log('XHR:', xhr);
        }

        statusBarSet('error', 'Error requesting job status change', 'pi-error');

        var show_html;
        if (xhr.status) {
            show_html = xhr.responseText;
        } else {
            show_html = $('<p>').addClass('text-danger').text(
              'Setting job status failed. There possibly was an error connecting to the server. ' +
              'Please check your network connection and try again.');
        }
        $('.job #item-action-panel .action-result-panel').html(show_html);
    });
}

/**
 * Request recreation / recompilation of the given job ID.
 */
 function recreateJob(job_id) {
    if (typeof job_id === 'undefined') {
        if (console) console.log("recreateJob(" + job_id + ") called");
        return;
    }

    project_url = ProjectUtils.projectUrl();
    if (typeof project_url === 'undefined') {
        throw new ReferenceError("ProjectUtils.projectUrl() undefined");
    }

    return $.post('/flamenco/' + project_url + '/jobs/' + job_id + '/recreate')
    .done(function(data) {
        if(console) console.log('Job recreate request OK');
        // Reload the entire page, since both the view-embed and the job list need refreshing.
        // However, if we have a task open now, that'll result in a 404 since the tasks will
        // be deleted.
        if (typeof document.body.dataset.taskId != 'undefined') {
            closeTaskDetails();
        }
        location.reload(true);
    })
    .fail(function(xhr) {
        if (console) {
            console.log('Error requesting recreation of job');
            console.log('XHR:', xhr);
        }

        statusBarSet('error', 'Error requesting job recreation', 'pi-error');

        var show_html;
        if (xhr.status) {
            show_html = xhr.responseText;
        } else {
            show_html = $('<p>').addClass('text-danger').text(
              'Job recompile request failed. There possibly was an error connecting to the server. ' +
              'Please check your network connection and try again.');
        }
        $('#item-action-panel .action-result-panel').html(show_html);
    });
 }

/**
  * Request re-queueing of all failed tasks of this job.
  */
function requeueFailedTasks(job_id) {
     if (typeof job_id === 'undefined') {
         if (console) console.log("requeueFailedTasks(" + job_id + ") called");
         return;
     }

     return $.ajax({
         method: 'PATCH',
         url: '/api/flamenco/jobs/' + job_id,
         contentType: 'application/json',
         data: JSON.stringify({'op': 'requeue-failed-tasks'}),
     })
     .done(function(data) {
         if(console) console.log('Re-queued all failed tasks');
         // Reload the entire page, since both the view-embed and the job list need refreshing.
         location.reload(true);
     })
     .fail(function(xhr) {
         if (console) {
             console.log('Error requesting re-queueing of failed tasks');
             console.log('XHR:', xhr);
         }

         statusBarSet('error', 'Error requesting re-queueing of failed tasks', 'pi-error');

         var show_html;
         if (xhr.status) {
             show_html = xhrErrorResponseElement(xhr, 'Failed task requeue request failed: ');
         } else {
             show_html = $('<p>').addClass('text-danger').text(
               'Failed task requeue request failed. There possibly was an error connecting to the server. ' +
               'Please check your network connection and try again.');
         }
         $('#item-action-panel .action-result-panel').html(show_html);
     });
}


/**
  * Request re-queueing of the task and its successors on the dependency graph.
  */
function requeueTaskAndSuccessors(task_id) {
    if (typeof task_id === 'undefined') {
        if (console) console.log("requeueTaskAndSuccessors(" + task_id + ") called");
        return;
    }
    return $.ajax({
            method: 'PATCH',
            url: '/api/flamenco/tasks/' + task_id,
            contentType: 'application/json',
            data: JSON.stringify({
                'op': 'requeue'
            }),
        })
        .done(function(data) {
            if (console) console.log('Re-queue task', task_id);
            // Reload the entire page, since both the view-embed and the job list need refreshing.
            location.reload(true);
        })
        .fail(function(xhr) {
            if (console) {
                console.log('Error requesting re-queueing task');
                console.log('XHR:', xhr);
            }
            statusBarSet('error', 'Error requesting re-queueing task', 'pi-error');
            var show_html;
            if (xhr.status) {
                show_html = xhrErrorResponseElement(xhr, 'Task requeue request failed: ');
            } else {
                show_html = $('<p>').addClass('text-danger').text(
                    'Task requeue request failed. There possibly was an error connecting to the server. ' +
                    'Please check your network connection and try again.');
            }
            $('#item-action-panel .action-result-panel').html(show_html);
        });
}

/**
 * Request cancellation or re-queueing of the given task ID.
 */
function setTaskStatus(task_id, new_status) {
    if (typeof task_id === 'undefined' || typeof new_status === 'undefined') {
        if (console) console.log("setTaskStatus(" + task_id + ", " + new_status + ") called");
        return;
    }

    project_url = ProjectUtils.projectUrl();
    return $.post('/flamenco/' + project_url + '/tasks/' + task_id + '/set-status', {status: new_status})
    .done(function(data) {
        if(console) console.log('Job set-status request OK');
        // Reload the entire page, since both the view-embed and the task list need refreshing.
        location.reload(true);
    })
    .fail(function(xhr) {
        if (console) {
            console.log('Error setting task status');
            console.log('XHR:', xhr);
        }

        statusBarSet('error', 'Error requesting task status change', 'pi-error');

        var show_html;
        if (xhr.status) {
            show_html = xhr.responseText;
        } else {
            show_html = $('<p>').addClass('text-danger').text(
              'Setting task status failed. There possibly was an error connecting to the server. ' +
              'Please check your network connection and try again.');
        }
        $('.task #task-action-panel .action-result-panel').html(show_html);
    });
}

/* Get the task log and populate the container */
function getTaskLog(url, container){
    if (typeof url === 'undefined' || typeof container === 'undefined') {
        if (console) console.log("getTaskLog(" + url + ", " + container + ") called");
        return;
    }

    var log_height = $('#col_main-overlay-content').height() - $('.flamenco-box.task').offset().top - $('.flamenco-box.task').height() - 100;

    $.get(url)
        .done(function(data) {
            if(console) console.log('Task log loaded OK\n' + url);
            $(container).html(data);

            var container_content = $(container).children('.item-log-content');
            $(container_content)
                .height(log_height)
                .scrollTop($(container_content).prop('scrollHeight'));
        })
        .fail(function(xhr) {
                if (console) {
                        console.log('Error fetching task log');
                        console.log('XHR:', xhr);
                }

                    statusBarSet('error', 'Opening task log failed.', 'pi-warning');

                if (xhr.status) {
                        $(container).html(xhr.responseText);
                } else {
                        $(container).html('<p class="text-danger">Opening task log failed. There possibly was ' +
                        'an error connecting to the server. Please check your network connection and ' +
                        'try again.</p>');
                }
        });
}


/**
 * Request archival of the given job ID.
 */
 function archiveJob(job_id) {
    if (typeof job_id === 'undefined') {
        if (console) console.log("archiveJob(" + job_id + ") called");
        return;
    }

    if (!confirm("Archiving a job is irreversible, are you sure you want to do this?")) {
        return;
    }

    return $.ajax({
        method: 'PATCH',
        url: '/api/flamenco/jobs/' + job_id,
        contentType: 'application/json',
        data: JSON.stringify({'op': 'archive-job'}),
    })
    .done(function(data) {
        if(console) console.log('Job archive request OK');
        // Reload the entire page, since both the view-embed and the job list need refreshing.
        location.reload(true);
    })
    .fail(function(xhr) {
        if (console) {
            console.log('Error requesting archival of job');
            console.log('XHR:', xhr);
        }

        statusBarSet('error', 'Error requesting job archival', 'pi-error');

        var show_html;
        if (xhr.status) {
            show_html = xhrErrorResponseElement(xhr, 'Job archival request failed: ');
        } else {
            show_html = $('<p>').addClass('text-danger').text(
              'Job archival request failed. There possibly was an error connecting to the server. ' +
              'Please check your network connection and try again.');
        }
        $('#item-action-panel .action-result-panel').html(show_html);
    });
 }

 /**
  * Request changing the job's priority.
  */
function changeJobPriority(job_id) {
    if (typeof job_id === 'undefined') {
        if (console) console.log("changeJobPriority(" + job_id + ") called");
        return;
    }

    var str_prio = prompt("What should the new priority be? A higher number means a higher priority.");
    if (!str_prio) return;
    var new_priority = parseInt(str_prio);
    if (new_priority != new_priority) {
        statusBarSet('error', 'Priority should be an integer.', 'pi-error');
        return;
    }

    $.ajax({
            method: 'PATCH',
            url: '/api/flamenco/jobs/' + job_id,
            contentType: 'application/json',
            data: JSON.stringify({
                'op': 'set-job-priority',
                'priority': new_priority
            }),
        })
        .done(function(data) {
            if (console) console.log('New job priority was accepted');
            // Reload the entire page, since both the view-embed and the job list need refreshing.
            location.reload(true);
        })
        .fail(function(xhr) {
            if (console) {
                console.log('Error requesting change of job priority');
                console.log('XHR:', xhr);
            }

            statusBarSet('error', 'Error requesting change of job priority', 'pi-error');

            var show_html;
            if (xhr.status) {
                show_html = xhrErrorResponseElement(xhr, 'Change in job priority failed: ');
            } else {
                show_html = $('<p>').addClass('text-danger').text(
                    'Change in job priority failed. There possibly was an error connecting to the server. ' +
                    'Please check your network connection and try again.');
            }
            $('#item-action-panel .action-result-panel').html(show_html);
        });
}
