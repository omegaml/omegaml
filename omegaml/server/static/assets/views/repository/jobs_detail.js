import CronView from "../../widgets/cronpick.js";

// server rendered variables
$(document).ready(function () {
  var resultsViewer = null;
  var scheduleViewer = null;
  const context = window.context;
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
      language: {
        emptyTable: "no data",
      },
      columns: [
        {
          data: "results",
          render: function (data, type, row, meta) {
            return `<a class="job-result" result-url="/jobs/${data}" href="/jobs/${data}">${data}</a>`;
          },
        },
        { data: "ts" },
        { data: "status" },
      ],
    });
    resultsViewer.ajax.reload(function (data) {
      // install click handler for job result links
      setInterval(function () {
        $(".job-result").click(function (e) {
          e.preventDefault();
          var result_url = $(e.target).attr("result-url");
          if (e.shiftKey) {
            window.open(result_url, "_blank");
          } else {
            $("#jobview-modal").attr("result-url", result_url);
            $("#jobview-modal").modal("show");
          }
        });
      }, 100);
    }, false);
  });
  // load job results into modal
  $("#jobview-modal").on("shown.bs.modal", function (e) {
    var result_url = $(e.target).attr("result-url");
    $("#jobview-modal .modal-body iframe").attr("src", result_url);
    $("#jobview-modal .modal-title").text(result_url);
  });
  $("#jobview-modal").on("hidden.bs.modal", function (e) {
    $("#jobview-modal .modal-body iframe").attr("src", "");
    $("#jobview-modal .modal-title").text("");
  });
  $("#schedule-tab").on("shown.bs.tab", function (e) {
    const cronView = new CronView({
      el: "#cronContainer",
      cronExpression: context.schedule.cron,
      events: {
        "cron:selected": function (event, data) {
          $("#cron-expression").val(data.cron);
        },
      },
    });
    cronView.render();
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
