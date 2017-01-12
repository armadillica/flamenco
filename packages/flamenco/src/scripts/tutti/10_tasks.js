/**
 * Open an item such as tasks/jobs in the #item-details div
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

    // Style elements starting with item_type and dash, e.g. "#job-uuid"
    $('[id^="' + item_type + '-"]').removeClass('active');
    $('#' + item_type + '-' + item_id).addClass('active');

    var item_url = '/flamenco/' + project_url + '/' + item_type + 's/' + item_id;
    var push_url = item_url;
    if (ProjectUtils.context() == 'job' && item_type == 'task'){
        push_url = '/flamenco/' + project_url + '/jobs/with-task/' + item_id;
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
function job_open(job_id, project_url)
{
    item_open(job_id, 'job', true, project_url);
}
function task_open(task_id, project_url)
{
    item_open(task_id, 'task', true, project_url);
}


window.onpopstate = function(event)
{
    var state = event.state;

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
        if(console) console.log('Tasks loaded OK');
        $('#tasks').html(data);
        setupJsTaskLinkClickHandlers();
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

$(function() {
    setupJsJobLinkClickHandlers()
    setupJsTaskLinkClickHandlers()
});

$(document).on('keyup', function(e){
    if (ProjectUtils.context() == 'job' || ProjectUtils.context() == 'task'){

        // Save on Ctrl + Enter anytime except when comments is on focus
        if ($('#comment_field') && $('#comment_field').not(':focus')){
            if ((e.keyCode == 10 || e.keyCode == 13) && e.ctrlKey){
                $("#item-save").trigger( "click" );
            }
        }
    }
});

/**
 * Request cancellation or re-queueing of the given job ID.
 */
function setJobStatus(job_id, new_status) {
    if (typeof job_id === 'undefined' || typeof new_status === 'undefined') {
        if (console) console.log("cancelJob(" + job_id + ", " + new_status + ") called");
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
        $('#job-action-panel .action-result-panel').html(show_html);
    });
}
