console.log("hello")
(function () {
    var myConnector = tableau.makeConnector();

    myConnector.getSchema = function (schemaCallback) {
        var cols = [
            { id: "status", dataType: tableau.dataTypeEnum.int },
            { id: "error_msg", dataType: tableau.dataTypeEnum.string },
            { id: "date", dataType: tableau.dataTypeEnum.datetime },
            { id: "lang", dataType: tableau.dataTypeEnum.string },
            { id: "stats_data_id", dataType: tableau.dataTypeEnum.string },
            { id: "data_format", dataType: tableau.dataTypeEnum.string },
            { id: "total_number", dataType: tableau.dataTypeEnum.int },
            { id: "from_number", dataType: tableau.dataTypeEnum.int },
            { id: "to_number", dataType: tableau.dataTypeEnum.int },
            { id: "next_key", dataType: tableau.dataTypeEnum.int },
            { id: "table_id", dataType: tableau.dataTypeEnum.string },
            { id: "stat_name_code", dataType: tableau.dataTypeEnum.string },
            { id: "stat_name", dataType: tableau.dataTypeEnum.string },
            { id: "gov_org_code", dataType: tableau.dataTypeEnum.string },
            { id: "gov_org", dataType: tableau.dataTypeEnum.string },
            { id: "statistics_name", dataType: tableau.dataTypeEnum.string },
            { id: "title_no", dataType: tableau.dataTypeEnum.string },
            { id: "title", dataType: tableau.dataTypeEnum.string },
            { id: "cycle", dataType: tableau.dataTypeEnum.string },
            { id: "survey_date", dataType: tableau.dataTypeEnum.string },
            { id: "open_date", dataType: tableau.dataTypeEnum.string },
            { id: "small_area", dataType: tableau.dataTypeEnum.int },
            { id: "collect_area", dataType: tableau.dataTypeEnum.string },
            { id: "main_category_code", dataType: tableau.dataTypeEnum.string },
            { id: "main_category", dataType: tableau.dataTypeEnum.string },
            { id: "sub_category_code", dataType: tableau.dataTypeEnum.string },
            { id: "sub_category", dataType: tableau.dataTypeEnum.string },
            { id: "overall_total_number", dataType: tableau.dataTypeEnum.int },
            { id: "updated_date", dataType: tableau.dataTypeEnum.string },
            { id: "table_category", dataType: tableau.dataTypeEnum.string },
            { id: "table_name", dataType: tableau.dataTypeEnum.string }
        ];
        let tableSchema = {
            id: "eStatData",
            alias: "e-Stat API Data",
            columns: cols
        };

        schemaCallback(tableSchema)
    };

    myConnector.getData = function (table, doneCallback) {

    };

    tableau.registerConnector(myConnector);
})();


document.querySelector("#getData")