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

    // Special case to highlight the job row when opening task in job context
    if (ProjectUtils.context() == 'job' && item_type == 'task'){
        $('[id^="job-"]').removeClass('active');
        $('#task-' + item_id).closest('.table-row').addClass('active');
    }

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


window.onpopstate = function(event)
{
    var state = event.state;

    item_open(state.itemId, state.itemType, false);
}

/**
 * Create a job and show it in the #item-details div.
 * NOTE: Not used at the moment, we're creating jobs via Blender
 */
function job_create(project_url)
{
    if (project_url === undefined) {
        throw new ReferenceError("job_create(" + project_url+ ") called.");
    }
    var url = '/flamenco/' + project_url + '/jobs/create';

    data = {
        project_url: project_url
    };

    $.post(url, data, function(job_data) {
        job_open(job_data.job_id);
    })
    .fail(function(xhr) {
        if (console) {
            console.log('Error creating task');
            console.log('XHR:', xhr);
        }
        $('#item-details').html(xhr.responseText);
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

function job_save(job_id, job_url) {
    return flamenco_form_save('job_form', 'job-' + job_id, job_url, {
        done: function($job, saved_job) {
            // Update the job list.
            $('.job-name-' + saved_job._id).text(saved_job.name);
            $job
                .removeClassPrefix('status-')
                .addClass('status-' + saved_job.status)
                .flashOnce()
            ;
            job_open(job_id);
        },
        fail: function($item, xhr_or_response_data) {
            if (xhr_or_response_data.status == 412) {
                // TODO: implement something nice here. Just make sure we don't throw
                // away the user's edits. It's up to the user to handle this.
            } else {
                $('#item-details').html(xhr_or_response_data.responseText);
            }
        },
        type: 'job'
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

function loadTasks(url) {
    return $.get(url)
  .done(function(data) {
      if(console) console.log('Tasks loaded OK');
      $('#tasks').html(data);
  })
}

$(function() {
    $("a.job-link[data-job-id]").click(function(e) {
        e.preventDefault();
        // delegateTarget is the thing the event hander was attached to,
        // rather than the thing we clicked on.
        var job_id = e.delegateTarget.dataset.jobId;
        job_open(job_id);
    });

    $("a.task-link[data-task-id]").click(function(e) {
        e.preventDefault();
        var task_id = e.delegateTarget.dataset.taskId;
        var project_url = e.delegateTarget.dataset.projectUrl;  // fine if undefined
        task_open(task_id, project_url);
    });
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
