import { JobRow } from './JobRow'
let RowObjectsSourceBase = pillar.vuecomponents.table.rows.RowObjectsSourceBase;

class ArchivedJobRowsSource extends RowObjectsSourceBase {
    constructor(projectId) {
        super();
        this.projectId = projectId;
    }

    thenGetRowObjects() {
        return flamenco.api.thenGetArchivedJobsInProject(this.projectId)
            .then((result) => {
                let jobs = result._items;
                this.rowObjects = jobs.map(j => new JobRow(j));
            });
    }
}

export { ArchivedJobRowsSource }
