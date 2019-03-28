let PillarTable = pillar.vuecomponents.table.PillarTable;
import {JobsColumnFactory} from './columns/JobsColumnFactory'
import {JobRowsSource} from './rows/JobRowsSource'
import {RowFilter} from './rows/filter/RowFilter'

/**
 * Flamenco jobs table
 * Table showing non-archived jobs for a project
 */
let JobsTable = Vue.component('flamenco-jobs-table', {
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
            rowsSource: new JobRowsSource(this.projectId),
        }
    },
    components: {
        'pillar-table-row-filter': RowFilter,
    },
});

export { JobsTable };
