/**
 * ExperimentView class extends BaseView to manage the display and interaction
 * of experiment data within a web application. It initializes components for
 * date range selection and paginated display of experiment runs, and binds
 * various event handlers for user interactions.
 *
 * The class provides functionality to:
 * - Initialize the date range picker and paginated grid view for experiment runs.
 * - Bind events for user actions such as selecting an experiment, showing tables,
 *   and plotting charts.
 * - Fetch and display experiment data in a table format, including handling
 *   server-side processing for large datasets.
 * - Plot charts based on selected experiment runs and specified date ranges.
 *
 * Key methods include:
 * - `initialize()`: Sets up the date range view and grid view, and binds events.
 * - `bindEvents()`: Attaches event listeners to UI elements for user interactions.
 * - `initializeTable()`: Configures and initializes the DataTable for displaying
 *   experiment data.
 * - `showRunCards()`: Fetches and displays experiment run cards based on the
 *   selected date range.
 * - `showTable()`: Fetches experiment data and initializes the table display.
 * - `plotChart()`: Fetches data for plotting charts based on selected runs.
 * - Event handlers for user actions such as clicking on experiments, showing
 *   tables, and plotting charts.
 *
 * This class is designed to work with the Plotly library for charting and
 * jQuery for DOM manipulation and AJAX requests.
 */
import Plotly from "../../plugins/plotly/plotly.module.js";
import BaseView from "../../widgets/baseview.js";
import DateRangeView from "../../widgets/sincepick.js";
import PaginatedRunGridView from "../../widgets/pagedcards.js";

class ExperimentView extends BaseView {
  constructor(options) {
    _.defaults(options, {
      events: {},
      experiments: [],
      templateUrl: url_for("static", {
        filename: "/assets/views/repository/experimentsview.html",
      }),
      el: "#experimentsView",
    });
    // DOM events
    _.extend(options.events, {
      "click .dropdown-item.exp": "onExperimentClick",
      "click #showtable": "onShowTableClick",
      "click #details": "onDetailsClick",
      "click #plotchart": "onPlotChartClick",
      "click #multicharts": "onMultiChartsClick",
    });
    super(options);
  }

  render(context) {
    super.render(context).then(() => {
      this.dateRangeView = new DateRangeView({
        el: "#exp-sinceRangePicker",
        events: {
          "since:selected": this.onSinceSelected.bind(this),
          "range:selected": this.onRangeSelected.bind(this),
        },
      });
      this.dateRangeView.render();

      this.gridView = new PaginatedRunGridView({
        el: "#expcards",
      });

      this.showTable("Experiment", true);
    });
  }

  onSinceSelected(event, data) {
    console.debug("since:selected", data);
    const exp = $("#dropdownExperiments").text();
    this.showTable(exp);
  }

  onRangeSelected(event, data) {
    console.debug("range:selected", data);
  }

  initializeTable(headers, exp, since, end, runs) {
    const columns = headers.map((header) => ({ data: header, title: header }));
    const summary = runs ? 0 : 1;

    $("#expviewer").DataTable({
      destroy: true,
      processing: true,
      serverSide: true,
      responsive: true,
      paging: true,
      select: true,
      pageLength: 50,
      layout: {
        topEnd: "paging",
      },
      ajax: {
        url: `${url_for("omega-server.tracking_api_experiment_data", {
          name: exp,
        })}?&since=${since}&end=${end}&summary=${summary}&run=${runs}`,
        type: "GET",
      },
      columns: columns,
    });
  }

  showRunCards(exp) {
    const since = this.dateRangeView.model.get("startDate");
    const end = this.dateRangeView.model.get("endDate");
    this.gridView.collection.url = `${url_for(
      "omega-server.tracking_api_experiment_data",
      { name: exp }
    )}?&since=${since}&end=${end}&summary=1`;
    this.gridView.collection.fetch({ reset: true });
    this.gridView.render();
  }

  showTable(exp, recreate = false, runs) {
    $("#expchart").hide();
    $("#exptable").show();
    $("#dropdownExperiments").text(exp || "Experiment");
    const since = this.dateRangeView.model.get("startDate");
    const end = this.dateRangeView.model.get("endDate");
    const summary = runs ? 0 : 1;

    $.ajax({
      url: `${url_for("omega-server.tracking_api_experiment_data", {
        name: exp,
      })}?initialize=1&summary=${summary}&since=${since}&end=${end}`,
      type: "GET",
      success: (json) => {
        $("#expviewer").DataTable().destroy();
        const headers = json.columns || Object.keys(json.data[0]);
        const thead = `<thead><tr>${headers
          .map((header) => `<th>${header}</th>`)
          .join("")}</tr></thead>`;
        $("#expviewer").html(thead);
        this.initializeTable(headers, exp, since, end, runs);
      },
    });
  }

  onExperimentClick(event) {
    const exp = $(event.currentTarget).data("value");
    this.showTable(exp);
  }

  onShowTableClick() {
    const exp = $("#dropdownExperiments").text();
    this.showTable(exp);
  }

  onDetailsClick() {
    const datatable = $("#expviewer").DataTable({ retrieve: true });
    const exp = $("#dropdownExperiments").text();
    const selected = datatable
      .rows({ selected: true })
      .data()
      .toArray()
      .map((row) => row.run);
    this.showTable(exp, true, selected);
  }

  plotChart(exp, since, end, multi = false) {
    const selected = $("#expviewer")
      .DataTable({ retrieve: true })
      .rows({ selected: true })
      .data()
      .toArray()
      .map((row) => row.run);
    $.ajax({
      dataType: "json",
      url: `${url_for("omega-server.tracking_api_plot_metrics", {
        name: exp,
      })}?multicharts=${
        multi ? 1 : 0
      }&since=${since}&end=${end}&runs=${selected}`,
      success: (data) => {
        $("#exptable").hide();
        $("#expchart").show();
        Plotly.newPlot("expchart", data, {});
      },
    });
  }

  onPlotChartClick() {
    const exp = $("#dropdownExperiments").text();
    const since = this.dateRangeView.model.get("startDate");
    const end = this.dateRangeView.model.get("endDate");
    this.plotChart(exp, since, end, false);
  }

  onMultiChartsClick() {
    const exp = $("#dropdownExperiments").text();
    const since = this.dateRangeView.model.get("startDate");
    const end = this.dateRangeView.model.get("endDate");
    this.plotChart(exp, since, end, true);
  }
}

export default ExperimentView;
