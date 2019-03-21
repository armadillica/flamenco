let RowFilterBase = pillar.vuecomponents.table.filter.RowFilter;
const TEMPLATE =`
<div class="pillar-table-row-filter">
    <input 
        placeholder="Filter by name"
        v-model="nameQuery"
    />
    <pillar-dropdown>
        <i class="pi-filter"
            slot="button"
            title="Row filter"
        />

        <ul class="settings-menu"
            slot="menu"
        >   
            <li>
                Status:
            </li>
            <li>
                <input type="checkbox"
                    v-model="showAssetStatus['active']"
                /> Active
            </li>
            <li>
                <input type="checkbox"
                    v-model="showAssetStatus['archived']"
                /> Archived
            </li>
            <li>
                <input type="checkbox"
                    v-model="showAssetStatus['archiving']"
                /> Archiving
            </li>
            <li>
                <input type="checkbox"
                    v-model="showAssetStatus['cancel-requested']"
                /> Cancel requested
            </li>
            <li>
                <input type="checkbox"
                    v-model="showAssetStatus['canceled']"
                /> Canceled
            </li>
            <li>
                <input type="checkbox"
                    v-model="showAssetStatus['construction-failed']"
                /> Construction failed
            </li>
            <li>
                <input type="checkbox"
                    v-model="showAssetStatus['completed']"
                /> Completed
            </li>
            <li>
                <input type="checkbox"
                    v-model="showAssetStatus['fail-requested']"
                /> Fail requested
            </li>
            <li>
                <input type="checkbox"
                    v-model="showAssetStatus['failed']"
                /> Failed
            </li>
            <li>
                <input type="checkbox"
                    v-model="showAssetStatus['paused']"
                /> Paused
            </li>
            <li>
                <input type="checkbox"
                    v-model="showAssetStatus['queued']"
                /> Queued
            </li>
            <li>
                <input type="checkbox"
                    v-model="showAssetStatus['requeued']"
                /> Requeued
            </li>
            <li>
                <input type="checkbox"
                    v-model="showAssetStatus['under-construction']"
                /> Under construction
            </li>
            <li>
                <input type="checkbox"
                    v-model="showAssetStatus['waiting-for-files']"
                /> Waiting for files
            </li>
        </ul>
    </pillar-dropdown>
</div>
`;

let RowFilter = {
    extends: RowFilterBase,
    template: TEMPLATE,
    props: {
        rowObjects: Array
    },
    data() {
        return {
            showAssetStatus: {
                'waiting-for-files': true,
                'under-construction': true,
                'construction-failed': true,
                'paused': true,
                'completed': true,
                'active': true,
                'canceled': true,
                'cancel-requested': true,
                'queued': true,
                'requeued': true,
                'failed': true,
                'fail-requested': true,
                'archiving': true,
                'archived': true,
            }
        }
    },
    computed: {
        nameQueryLoweCase() {
            return this.nameQuery.toLowerCase();
        },
        visibleRowObjects() {
            return this.rowObjects.filter((row) => {
                if (!this.hasShowStatus(row)) return false;
                return this.filterByName(row);
            });
        }
    },
    methods: {
        hasShowStatus(rowObject) {
            let status = rowObject.getStatus();
            return !(this.showAssetStatus[status] === false); // To handle invalid statuses
        },
    },
};

export { RowFilter }
