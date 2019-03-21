let ColumnBase = pillar.vuecomponents.table.columns.ColumnBase;
let CellDefault = pillar.vuecomponents.table.cells.renderer.CellDefault;

class Status extends ColumnBase {
    constructor() {
        super('Status', 'job-status');
        this.isMandatory = false;
    }

    /**
     * @param {JobRow} rowObject 
     * @returns {String} cell renderer name
     */
    getCellRenderer(rowObject) {
        return CellDefault.options.name;
    }

    /**
     * @param {JobRow} rowObject 
     * @returns {String} status
     */
    getRawCellValue(rowObject) {
        return rowObject.getStatus();
    }

    /**
     * @param {String} rawCellValue status string
     * @param {JobRow} rowObject 
     * @returns {String} cell tooltip
     */
    getCellTitle(rawCellValue, rowObject) {
        function capitalize(str) {
            if(str.length === 0) return str;
            return str.charAt(0).toUpperCase() + str.slice(1);
        }
        let formatedStatus = capitalize(rawCellValue).replace('-', ' ');
        return `Status: ${formatedStatus}`;
    }

    /**
     * @param {String} rawCellValue status string
     * @param {JobRow} rowObject 
     * @returns {Object} css classes object
     */
    getCellClasses(rawCellValue, rowObject) {
        let classes = super.getCellClasses(rawCellValue, rowObject);
        classes[`status-${rawCellValue}`] = true;
        return classes;
    }
}

export { Status }
