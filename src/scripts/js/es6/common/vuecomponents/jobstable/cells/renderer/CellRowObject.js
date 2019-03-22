let CellDefault = pillar.vuecomponents.table.cells.renderer.CellDefault;

const TEMPLATE =`
<div>
    <a
        @click="ignoreDefault" 
        :href="cellLink"
        :title="cellValue"
    >
        {{ cellValue }}
    </a>
</div>
`;

let CellRowObject = Vue.component('pillar-cell-row-object', {
    extends: CellDefault,
    template: TEMPLATE,
    computed: {
        cellLink() {
            return `/flamenco/jobs/${this.rowObject.getId()}/redir`;
        }
    },
    methods: {
        ignoreDefault(event) {
            // Don't follow link, let the event bubble and the row handles it
            event.preventDefault();
        }
    },
});

export { CellRowObject }
