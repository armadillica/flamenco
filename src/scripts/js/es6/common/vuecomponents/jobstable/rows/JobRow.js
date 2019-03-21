let RowBase = pillar.vuecomponents.table.rows.RowBase;

/**
 * Managers are not embeddable so we need to fetch them seperatly. But since many jobs has the same manager we cache
 * the requests.
 */
class ManagerCache {
    constructor() {
        this._managerPromiseMap = {};
    }

    thenGetManager(managerId) {
        this._managerPromiseMap[managerId] = this._managerPromiseMap[managerId] || flamenco.api.thenGetManager(managerId);
        return this._managerPromiseMap[managerId];
    }
}

const MANAGER_CACHE = new ManagerCache();

class JobRow extends RowBase {
    constructor(underlyingObject) {
        super(underlyingObject);
        this._manager = {name: '-unknown-'};
    }

    _thenInitImpl() {
        return MANAGER_CACHE.thenGetManager(this.underlyingObject.manager)
            .then((manager => this._manager = manager))
            .catch(err => {
                if (err.status === 403 /* no permission, but that is not a problem */) {
                    return;
                } else {
                    throw err;
                }
            });
    }

    getPriority() {
        return this.underlyingObject.priority || 0;
    }

    getStatus() {
        return this.underlyingObject.status || '';
    }

    getManager() {
        return this._manager;
    }
}

export { JobRow }
