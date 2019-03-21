import { JobRow } from './JobRow'
let RowObjectsSourceBase = pillar.vuecomponents.table.rows.RowObjectsSourceBase;

class JobRowsSource extends RowObjectsSourceBase {
    constructor(projectId) {
        super();
        this.projectId = projectId;
    }

    thenGetRowObjects() {
        return flamenco.api.thenGetJobsInProject(this.projectId)
            .then((result) => {
                let jobs = result._items;
                this.rowObjects = jobs.map(j => new JobRow(j));
            });
    }
}

export { JobRowsSource }
