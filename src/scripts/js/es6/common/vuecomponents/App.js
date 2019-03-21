import {JobsTable} from './jobstable/JobsTable'
import {ArchivedJobsTable} from './jobstable/ArchivedJobsTable'

const TEMPLATE =`
<div class="flamenco-app">
    <component
        :is="tableComponentName"
        :projectId="projectId"
        :selectedIds="selectedIds"
        @selectItemsChanged="onSelectItemsChanged"
    />
</div>
`;

Vue.component('flamenco-app', {
    template: TEMPLATE,
    props: {
        projectId: String,
        selectedIds: {
            type: Array,
            default: []
        },
        context: { // job or archive
            type: String,
            default: 'job'
        }
    },
    created() {
        window.onpopstate = this.onPopState;
    },
    computed: {
        tableComponentName() {
            switch (this.context) {
                case 'archive': return ArchivedJobsTable.options.name;
                case 'job': return JobsTable.options.name;
                default:
                    console.warn(`Unknown flamenco app context: ${this.context}`);
                    return JobsTable.options.name;
            }
        },
    },
    methods: {
        onSelectItemsChanged(selectedJobs) {
            let job = selectedJobs[0];
            if (job) {
                let userClickedInTable = this.selectedIds[0] !== job._id;
                if (userClickedInTable) {
                    item_open(job._id, 'job', true);
                } else {
                    // item is already open
                }
                this.selectedIds = [job._id];
            }
        },
        /**
         * Called when user clicks back/forward in browser.
         * @param {PopStateEvent} event 
         */
        onPopState(event) {
            let state = event.state;
            if (state && state.itemType === 'job') {
                this.selectedIds = [state.itemId];
            }
            defaultFlamencoPopstate(event);
        }
    },
});
