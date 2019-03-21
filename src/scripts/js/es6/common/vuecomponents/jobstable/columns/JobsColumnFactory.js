import { RowObject } from "./RowObject";
import { Priority } from "./Priority";
import { Status } from "./Status";
import { Manager } from "./Manager";

let ColumnFactoryBase = pillar.vuecomponents.table.columns.ColumnFactoryBase;


class JobsColumnFactory extends ColumnFactoryBase{
    constructor() {
        super();
    }

    thenGetColumns() {
        return Promise.resolve([
            new Status(),
            new RowObject(),
            new Manager(),
            new Priority(),
        ]);
    }
}

export { JobsColumnFactory }
