let PillarTable = pillar.vuecomponents.table.PillarTable;
import {JobsColumnFactory} from './columns/JobsColumnFactory'
import {ArchivedJobRowsSource} from './rows/ArchivedJobRowsSource'

/**
 * Flameco archived jobs
 * Showing archived jobs for a project
 */
let ArchivedJobsTable = Vue.component('flamenco-archive-table', {
    extends: PillarTable,
    props: {
        projectId: String,
        canMultiSelect: {
            type: Boolean,
            default: false
        }
    },
    data() {
        return {
            columnFactory: new JobsColumnFactory(this.projectId),
            rowsSource: new ArchivedJobRowsSource(this.projectId),
        }
    },
});

export { ArchivedJobsTable };
