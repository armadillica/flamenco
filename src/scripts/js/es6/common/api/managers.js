/**
 * @param {String} managerId 
 * @returns {Promise} resolves to a flamenco manager object
 */
function thenGetManager(managerId) {
    return $.ajax({
        url: `/api/flamenco/managers/${managerId}`,
        cache: false,
    });
}

export {thenGetManager}
