// server rendered variables
$(document).ready(function () {
    var resultsViewer = null;
    // build experiment data viewer on showing tab
    $('#results-tab').on('shown.bs.tab', function (e) {
      resultsViewer = resultsViewer || $("#results-viewer").DataTable({
      ajax: `/jobs/runs/${context.name}`,
      serverSide: true,
      search: {
        return: true,
      },
      processing: true,
      responsive: true,
      //scrollX: true,
      columns: [
        { data: "results",
          render: function (data, type, row, meta) {
            return `<a href="/jobs/${data}" target=_blank>${data}</a>`;
          },
        },
        { data: "ts" },
        { data: "status" },
      ],
    }); // DataTable
    }); // shown.bs.tab
  });