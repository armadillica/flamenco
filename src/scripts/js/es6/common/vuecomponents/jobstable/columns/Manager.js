let ColumnBase = pillar.vuecomponents.table.columns.ColumnBase;
let CellDefault = pillar.vuecomponents.table.cells.renderer.CellDefault;

class Manager extends ColumnBase {
    constructor() {
        super('Manager', 'job-manager');
        this.isMandatory = false;
    }

    /**
     * @param {JobRow} rowObject 
     * @returns {String} cell renderer
     */
    getCellRenderer(rowObject) {
        return CellDefault.options.name;
    }

    /**
     * @param {JobRow} rowObject 
     * @returns {String} job manager name
     */
    getRawCellValue(rowObject) {
        return rowObject.getManager().name || '';
    }
}

export { Manager }
