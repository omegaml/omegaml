// Paginated Run Collection
const PaginatedRunCollection = Backbone.Collection.extend({
  model: Run,

  initialize: function (models, options) {
    this.pageSize = options?.pageSize || 12;
    this.currentPage = 1;
    this.totalRecords = 0;
    this.sortColumn = "date";
    this.sortDirection = "desc";
    this.filters = {};

    // Keep track of selected runs across pages
    this.selectedRuns = new Set();
  },

  url: function () {
    // Construct URL with pagination, sorting, and filtering parameters
    const baseUrl = "/api/runs"; // Change to your API endpoint
    const params = new URLSearchParams({
      page: this.currentPage,
      pageSize: this.pageSize,
      sortColumn: this.sortColumn,
      sortDirection: this.sortDirection,
      ...this.filters,
    });
    return `${baseUrl}?${params.toString()}`;
  },

  parse: function (response) {
    this.totalRecords = response.total;
    this.totalPages = Math.ceil(this.totalRecords / this.pageSize);
    return response.data;
  },

  getSelected: function () {
    return Array.from(this.selectedRuns).map(
      (id) => this.get(id) || { id } // Return at least the ID if run is not in current page
    );
  },
});

// Updated Grid View with Pagination
const PaginatedRunGridView = Backbone.View.extend({
  className: "container-fluid",

  template: _.template(`
        <div class="row mb-3">
            <div class="col-md-6">
                <div class="d-flex align-items-center">
                    <button class="btn btn-outline-primary btn-sm me-2 select-all-page">
                        Select Page
                    </button>
                    <button class="btn btn-outline-secondary btn-sm clear-selection">
                        Clear Selection
                    </button>
                    <span class="ms-3">
                        Selected: <span class="badge bg-primary selection-count">0</span>
                    </span>
                </div>
            </div>
            <div class="col-md-6">
                <div class="input-group">
                    <input type="text" class="form-control search-input" 
                           placeholder="Search runs...">
                    <select class="form-select status-filter" style="max-width: 150px;">
                        <option value="">All Status</option>
                        <option value="completed">Completed</option>
                        <option value="running">Running</option>
                        <option value="failed">Failed</option>
                    </select>
                </div>
            </div>
        </div>
        <div class="row runs-container"></div>
        <div class="row mt-3">
            <div class="col-md-6">
                <div class="showing-info">
                    Showing <%= startRecord %>-<%= endRecord %> of <%= totalRecords %> runs
                </div>
            </div>
            <div class="col-md-6">
                <nav aria-label="Run navigation" class="float-end">
                    <ul class="pagination pagination-sm"></ul>
                </nav>
            </div>
        </div>
    `),

  events: {
    "click .select-all-page": "selectAllPage",
    "click .clear-selection": "clearSelection",
    "input .search-input": "debounceSearch",
    "change .status-filter": "filterByStatus",
    "click .page-link": "changePage",
  },

  initialize: function (options) {
    this.collection = options.collection;
    this.cardViews = [];

    this.debounceSearch = _.debounce(this.search, 300);

    this.listenTo(this.collection, "sync", this.render);
    this.listenTo(this.collection, "error", this.handleError);

    // Initial fetch
    this.collection.fetch({ reset: true });
  },

  render: function () {
    const startRecord =
      (this.collection.currentPage - 1) * this.collection.pageSize + 1;
    const endRecord = Math.min(
      startRecord + this.collection.pageSize - 1,
      this.collection.totalRecords
    );

    this.$el.html(
      this.template({
        startRecord,
        endRecord,
        totalRecords: this.collection.totalRecords,
      })
    );

    this.$runsContainer = this.$(".runs-container");
    this.renderCards();
    this.renderPagination();
    this.updateSelectionCount();

    return this;
  },

  renderCards: function () {
    this.$runsContainer.empty();
    this.cardViews = [];

    this.collection.each((run) => {
      // Set selected state based on global selection tracking
      run.set("selected", this.collection.selectedRuns.has(run.id), {
        silent: true,
      });

      const view = new RunCardView({ model: run });
      this.cardViews.push(view);
      this.listenTo(view, "selectionChanged", this.onSelectionChanged);
      this.$runsContainer.append(view.render().el);
    });
  },

  renderPagination: function () {
    const $pagination = this.$(".pagination");
    $pagination.empty();

    if (this.collection.totalPages <= 1) return;

    // Previous button
    $pagination.append(`
            <li class="page-item ${
              this.collection.currentPage === 1 ? "disabled" : ""
            }">
                <a class="page-link" href="#" data-page="${
                  this.collection.currentPage - 1
                }">
                    Previous
                </a>
            </li>
        `);

    // Page numbers
    for (let i = 1; i <= this.collection.totalPages; i++) {
      if (
        i === 1 ||
        i === this.collection.totalPages ||
        (i >= this.collection.currentPage - 2 &&
          i <= this.collection.currentPage + 2)
      ) {
        $pagination.append(`
                    <li class="page-item ${
                      i === this.collection.currentPage ? "active" : ""
                    }">
                        <a class="page-link" href="#" data-page="${i}">${i}</a>
                    </li>
                `);
      } else if (
        i === this.collection.currentPage - 3 ||
        i === this.collection.currentPage + 3
      ) {
        $pagination.append(`
                    <li class="page-item disabled">
                        <span class="page-link">...</span>
                    </li>
                `);
      }
    }

    // Next button
    $pagination.append(`
            <li class="page-item ${
              this.collection.currentPage === this.collection.totalPages
                ? "disabled"
                : ""
            }">
                <a class="page-link" href="#" data-page="${
                  this.collection.currentPage + 1
                }">
                    Next
                </a>
            </li>
        `);
  },

  changePage: function (e) {
    e.preventDefault();
    const $link = $(e.currentTarget);
    const page = parseInt($link.data("page"));

    if (page && page !== this.collection.currentPage) {
      this.collection.currentPage = page;
      this.collection.fetch({ reset: true });
    }
  },

  search: function (e) {
    const searchTerm = e.target.value.trim();
    if (searchTerm) {
      this.collection.filters.search = searchTerm;
    } else {
      delete this.collection.filters.search;
    }
    this.collection.currentPage = 1;
    this.collection.fetch({ reset: true });
  },

  filterByStatus: function (e) {
    const status = e.target.value;
    if (status) {
      this.collection.filters.status = status;
    } else {
      delete this.collection.filters.status;
    }
    this.collection.currentPage = 1;
    this.collection.fetch({ reset: true });
  },

  selectAllPage: function () {
    this.collection.each((run) => {
      this.collection.selectedRuns.add(run.id);
      run.set("selected", true);
    });
    this.updateSelectionCount();
  },

  clearSelection: function () {
    this.collection.selectedRuns.clear();
    this.collection.each((run) => run.set("selected", false));
    this.updateSelectionCount();
  },

  onSelectionChanged: function (model) {
    if (model.get("selected")) {
      this.collection.selectedRuns.add(model.id);
    } else {
      this.collection.selectedRuns.delete(model.id);
    }
    this.updateSelectionCount();
    this.trigger("selection:changed", this.collection.getSelected());
  },

  updateSelectionCount: function () {
    this.$(".selection-count").text(this.collection.selectedRuns.size);
  },

  handleError: function (collection, response) {
    console.error("Error fetching runs:", response);
    // Add your error handling logic here
  },
});

// Example server response format:
/*
{
    "data": [
        {
            "id": "run_1",
            "name": "Experiment Run 1",
            "date": "2024-01-01",
            "status": "completed",
            "metrics": {
                "accuracy": 0.95,
                "loss": 0.23,
                "f1_score": 0.94
            },
            "tags": ["model_v1", "dataset_a"]
        },
        // ... more runs ...
    ],
    "total": 1000,  // Total number of records
    "page": 1,      // Current page
    "pageSize": 12  // Records per page
}
*/

// Example usage:
/*
const runs = new PaginatedRunCollection([], {
    pageSize: 12
});

const gridView = new PaginatedRunGridView({ collection: runs });
$('#app').append(gridView.render().el);

gridView.on('selection:changed', function(selectedRuns) {
    console.log('Selected runs:', selectedRuns);
    // Update your plots or perform other actions
});
*/

export default PaginatedRunGridView;
