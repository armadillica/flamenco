let NameFilter = pillar.vuecomponents.table.rows.filter.NameFilter;
let StatusFilter = pillar.vuecomponents.table.rows.filter.StatusFilter;

const TEMPLATE =`
<div class="pillar-table-row-filter">
    <name-filter 
        :rowObjects="rowObjects"
        :componentState="(componentState || {}).nameFilter"
        @visible-row-objects-changed="onNameFiltered"
        @component-state-changed="onNameFilterStateChanged"
    />
    <status-filter
        :availableStatuses="availableStatuses"
        :rowObjects="nameFilteredRowObjects"
        :componentState="(componentState || {}).statusFilter"
        @visible-row-objects-changed="$emit('visible-row-objects-changed', ...arguments)"
        @component-state-changed="onStatusFilterStateChanged"
    />
</div>
`;

const JOB_STATUSES = [
    'waiting-for-files',
    'under-construction',
    'construction-failed',
    'paused',
    'completed',
    'active',
    'canceled',
    'cancel-requested',
    'queued',
    'requeued',
    'failed',
    'fail-requested',
    'archiving',
    'archived',
];


let RowFilter = {
    template: TEMPLATE,
    props: {
        rowObjects: Array,
        componentState: Object
    },
    data() {
        return {
            availableStatuses: JOB_STATUSES,
            nameFilteredRowObjects: [],
            nameFilterState: (this.componentState || {}).nameFilter,
            statusFilterState: (this.componentState || {}).statusFilter,
        }
    },
    methods: {
        onNameFiltered(visibleRowObjects) {
            this.nameFilteredRowObjects = visibleRowObjects;
        },
        onNameFilterStateChanged(stateObj) {
            this.nameFilterState = stateObj;
        },
        onStatusFilterStateChanged(stateObj) {
            this.statusFilterState = stateObj;
        }
    },
    computed: {
        currentComponentState() {
            return {
                nameFilter: this.nameFilterState,
                statusFilter: this.statusFilterState,
            };
        }
    },
    watch: {
        currentComponentState(newValue) {
            this.$emit('component-state-changed', newValue);
        }
    },
    components: {
        'name-filter': NameFilter,
        'status-filter': StatusFilter
    }
};

export { RowFilter }
