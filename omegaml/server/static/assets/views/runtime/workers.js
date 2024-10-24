$(document).ready(function () {
  let workerId = null;
  let refreshInterval = null;
  $("#list-table").DataTable();
  $("#logviewer").DataTable({
    ajax: "/runtime/log",
    serverSide: true,
    search: {
      return: true,
    },
    processing: true,
    responsive: true,
    columns: [
      { data: "text" },
      { data: "hostname" },
      { data: "userid" },
      { data: "logger" },
    ],
  });
  $(".worker-item").click(function () {
    workerId = $(this).attr("worker-id");
    $("#worker-modal").modal("show");
  });
  $("#worker-modal").on("shown.bs.modal", function (e) {
    function refresh() {
      $.ajax({
        url: "/runtime/worker/" + workerId,
        success: function (data) {
          $("#worker-modal .modal-title").text(data.id);
          $("#worker-modal .modal-body").html(data);
        },
      });
    }
    refresh();
    refreshInterval = setInterval(refresh, 2000);
  });
  $("#worker-modal").on("hidden.bs.modal", function (e) {
    workerId = null;
    clearInterval(refreshInterval);
  });
});
