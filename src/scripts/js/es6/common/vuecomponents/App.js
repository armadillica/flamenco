import {JobsTable} from './jobstable/JobsTable'
import {ArchivedJobsTable} from './jobstable/ArchivedJobsTable'

const TEMPLATE =`
<div class="flamenco-app">
    <component
        :is="tableComponentName"
        :projectId="projectId"
        :selectedIds="currentSelectedIds"
        :componentState="initialTableState"
        @selectItemsChanged="onSelectItemsChanged"
        @componentStateChanged="onTableStateChanged"
    />
</div>
`;

class ComponentState {
    /**
     * Serializable state of this component.
     *
     * @param {Object} tableState
     */
    constructor(tableState) {
        this.tableState = tableState;
    }
}

/**
 * Component wrapping a table for selecting flamenco_jobs documents.
 * Selected row filters and visible columns are stored in localStorage per project/context. This makes the settings
 * sticky between sessions in the same browser.
 * Selected nodes are stored in window.history by item_open.
 */
Vue.component('flamenco-app', {
    template: TEMPLATE,
    props: {
        projectId: String,
        selectedIds: {
            type: Array,
            default: () => {return []}
        },
        context: { // job or archive
            type: String,
            default: 'job'
        }
    },
    data() {
        return {
            currentSelectedIds: this.selectedIds,
        };
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
        stateStorageKey() {
            return `flamenco.${this.projectId}.${this.context}`;
        },
        initialAppState() {
            let stateJsonStr;
            try {
                stateJsonStr = localStorage.getItem(this.stateStorageKey);
            } catch (error) {
                // Log and ignore.
                console.warn('Unable to restore state:', error);
            }
            return stateJsonStr ? JSON.parse(stateJsonStr) : undefined;
        },
        initialTableState() {
            return this.initialAppState ? this.initialAppState.tableState : undefined;
        }
    },
    methods: {
        onSelectItemsChanged(selectedJobs) {
            let job = selectedJobs[0];
            if (job) {
                let userClickedInTable = this.currentSelectedIds[0] !== job._id;
                if (userClickedInTable) {
                    item_open(job._id, 'job', true); // defined in 10_tasks.js
                } else {
                    // item is already open
                }
                this.currentSelectedIds = [job._id];
            }
        },
        /**
         * Save table state to localStorage per project and context
         * @param {Object} newState
         */
        onTableStateChanged(newState) {
            let appState = new ComponentState(newState);
            let stateJsonStr = JSON.stringify(appState);
            try {
                localStorage.setItem(this.stateStorageKey, stateJsonStr);
            } catch (error) {
                // Log and ignore.
                console.warn('Unable to save state:', error);
            }
        },
        /**
         * Called when user clicks back/forward in browser.
         * @param {PopStateEvent} event
         */
        onPopState(event) {
            let state = event.state;
            if (state && state.itemType === 'job') {
                this.currentSelectedIds = [state.itemId];
            }
            defaultFlamencoPopstate(event);
        }
    },
});
