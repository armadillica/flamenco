let ColumnBase = pillar.vuecomponents.table.columns.ColumnBase;
import { CellRowObject } from '../cells/renderer/CellRowObject'

class RowObject extends ColumnBase {
    constructor() {
        super('Name', 'row-object');
        this.isMandatory = true;
    }
    /**
     * @param {JobRow} rowObject 
     * @returns {String} cell renderer
     */
    getCellRenderer(rowObject) {
        return CellRowObject.options.name;
    }

    /**
     * @param {JobRow} rowObject 
     * @returns {String}
     */
    getRawCellValue(rowObject) {
        return rowObject.getName() || '<No Name>';
    }
}

export { RowObject }
