// server rendered variables
$(document).ready(function () {
  var resultsViewer = null;
  var scheduleViewer = null;
  // build experiment data viewer on showing tab
  $("#results-tab").on("shown.bs.tab", function (e) {
    resultsViewer ? resultsViewer.ajax.reload() : null;
    resultsViewer = $("#results-viewer").DataTable({
      ajax: `/jobs/runs/${context.name}`,
      retrieve: true, // if already initialized, return the instance
      serverSide: true,
      search: {
        return: true,
      },
      processing: true,
      responsive: true,
      //scrollX: true,
      columns: [
        {
          data: "results",
          render: function (data, type, row, meta) {
            return `<a href="/jobs/${data}" target=_blank>${data}</a>`;
          },
        },
        { data: "ts" },
        { data: "status" },
      ],
    });
  });
  $("#schedule-tab").on("shown.bs.tab", function (e) {
    scheduleViewer ? scheduleViewer.ajax.reload() : null;
    scheduleViewer = $("#schedule-viewer").DataTable({
      retrieve: true, // if already initialized, return the instance
      ajax: {
        url: `/jobs/schedule/${context.name}`,
        dataSrc: function (data) {
          console.log("schedule data", data);
          return data.data.triggers;
        },
      },
      search: {
        return: true,
      },
      processing: true,
      responsive: true,
      //scrollX: true,
      columns: [
        { data: "event" },
        { data: "event-kind" },
        { data: "run-at" },
        { data: "status" },
      ],
    }); // DataTable
  }); // shown.bs.tab
});
