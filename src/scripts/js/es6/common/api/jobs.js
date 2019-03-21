/**
 * @param {String} projectId 
 * @returns {Promise} resolves to a eve list with archived jobs
 */
function thenGetJobsInProject(projectId) {
    let where = {
        project: projectId,
        status: {'$ne': 'archived'}
    }
    let sort = '-_updated';

    let encodedWhere = encodeURIComponent(JSON.stringify(where));
    let encodedSort = encodeURIComponent(sort);

    return $.ajax({
        url: `/api/flamenco/jobs?where=${encodedWhere}&sort=${encodedSort}`,
        cache: false,
    });
}

/**
 * @param {String} projectId 
 * @returns {Promise} resolves to a eve list with archived jobs
 */
function thenGetArchivedJobsInProject(projectId) {
    let where = {
        project: projectId,
        status: 'archived'
    }
    let sort = '-_updated';

    let encodedWhere = encodeURIComponent(JSON.stringify(where));
    let encodedSort = encodeURIComponent(sort);

    return $.ajax({
        url: `/api/flamenco/jobs?where=${encodedWhere}&sort=${encodedSort}`,
        cache: false,
    });
}

export { thenGetJobsInProject, thenGetArchivedJobsInProject }
