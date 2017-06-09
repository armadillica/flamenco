function unlinkProject(manager_id, project_id) {
    if (typeof project_id == 'undefined') {
        throw 'unlinkProject() with undefined project_id called';
    }
    return patchManager(manager_id, {
        op: 'remove-from-project',
        project: project_id,
    })
    .fail(function(err) {
        var $p = xhrErrorResponseElement(err, 'Error unlinking project: ');
        toastr.error('Error unlinking project', $p);
    })
    ;
}

function linkProject(manager_id, project_id) {
    if (typeof project_id == 'undefined') {
        throw 'linkProject() with undefined project_id called';
    }
    return patchManager(manager_id, {
        op: 'assign-to-project',
        project: project_id,
    })
    .fail(function(err) {
        var $p = xhrErrorResponseElement(err, 'Error linking project: ');
        toastr.error('Error linking project', $p);
    })
    ;
}

function patchManager(manager_id, patch) {
    if (typeof manager_id == 'undefined') {
        throw 'patchManager(undefined, ...) called';
    }
    if (typeof patch == 'undefined') {
        throw 'patchManager(manager_id, undefined) called';
    }

    if (console) console.log('patchManager', manager_id, patch);

    var promise = $.ajax({
        url: '/api/flamenco/managers/' + manager_id,
        method: 'PATCH',
        contentType: 'application/json',
        data: JSON.stringify(patch),
    })
    .done(function() {
        if (console) console.log('PATCH', manager_id, 'OK');
    })
    .fail(function(err) {
        if (console) console.log('Error patching: ', err);
    })
    ;

    return promise;
}
