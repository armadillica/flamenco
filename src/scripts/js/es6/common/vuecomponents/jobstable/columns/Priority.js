let ColumnBase = pillar.vuecomponents.table.columns.ColumnBase;
let CellDefault = pillar.vuecomponents.table.cells.renderer.CellDefault;

class Priority extends ColumnBase {
    constructor() {
        super('Priority', 'job-priority');
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
     * @returns {Integer} job priority
     */
    getRawCellValue(rowObject) {
        return rowObject.getPriority();
    }
}

export { Priority }
