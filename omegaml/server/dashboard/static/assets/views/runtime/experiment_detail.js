// executionView.js
//import { ExecutionModel } from "./executionModel.js";
import BaseView from "../../widgets/baseview.js";

export class ExecutionView extends BaseView {
  constructor(options) {
    _.defaults(options, {
      events: {},
      templateUrl: url_for("static", {
        filename: "/assets/views/runtime/experiment_detail.html",
      }),
      el: "#experimentDetailView",
    });
    // DOM events
    _.extend(options.events, {
      "click .step-item": "onStepClick",
      "click #show-all-steps": "onAllStepsClick",
    });
    super(options);
    this.model = options.context;
  }

  getEventsData(experiment, run) {
    return $.ajax({
      dataType: "json",
      url: `${url_for("omega-server.tracking_api_experiment_data", {
        name: experiment,
      })}?&run=${run}`,
    }).then((data) => {
      return this.convertEvents2Request(data.data);
    });
  }

  convertEvents2Request(events) {
    // Find the event with name 'task_call', or fallback to the first event
    const inputEvent =
      _.find(events, (e) => e.event === "task_call") || _.first(events) || {};
    const outputEvent =
      _.find(events, (e) => e.event === "task_success") || _.last(events) || {};
    // Calculate duration in seconds from inputEvent.dt and outputEvent.dt (ISO format)
    let startedAt = new Date(inputEvent.dt);
    let completedAt = new Date(outputEvent.dt);
    let totalDuration = Math.round((completedAt - startedAt) / 1000); // seconds
    return {
      input: inputEvent.value || {},
      output: outputEvent.value || {},
      status: (outputEvent.event || "unknown").replace("task_", ""),
      total_duration: totalDuration,
      started_at: startedAt,
      completed_at: completedAt,
      steps: events.map((event, index) => ({
        id: index,
        name: event.event,
        status: event.status || "unknown",
        duration: event.duration || 0,
        percentage: event.percentage || 0,
        input: event.input || {},
        output: event.value || {},
        metrics: event.metrics || {},
        logs: event.logs || "",
      })),
    };
  }

  // Render the view
  render(context) {
    const request = this.model.request || this.sampleData().request;
    context = _.defaults(context || {}, this.options.context);
    const promise = this.getEventsData(context.experiment, context.run).then(
      (request) => {
        this.model.request = request;
        context.req = request;
        context.steps = request.steps || [];
        console.debug("Rendering execution view with context:", context);
        super.render(context).then(() => {});
      }
    );
    return promise;
  }

  onAllStepsClick(event) {
    event.preventDefault();
    this.render({});
  }

  onStepClick(event) {
    const stepId = $(event.currentTarget).data("step-id");
    const request = this.model.request || this.sampleData().request;
    const step = request.steps.find((s) => s.id === stepId);
    if (!step) return;
    super
      .render({
        req: step,
        steps: this.model.request.steps || [],
        formatDuration: this.formatDuration,
      })
      .then(() => {
        $(".step-item").removeClass("active");
        $(`.step-item[data-step-id="${stepId}"]`).addClass("active");
      });
  }

  // Format duration
  formatDuration(ms) {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    if (minutes > 0) {
      return `${minutes}m ${remainingSeconds}s`;
    }
    return `${remainingSeconds}s`;
  }

  sampleData() {
    const executionData = {
      request: {
        input: {
          dataset: "customer_behavior_2024.csv",
          target: "purchase_probability",
          algorithm: "XGBoost",
          validation_split: 0.2,
          hyperparameters: {
            max_depth: 6,
            learning_rate: 0.1,
            n_estimators: 100,
          },
        },
        output: {
          model_id: "model_20250115_v1.2",
          accuracy: 0.912,
          precision: 0.89,
          recall: 0.76,
          f1_score: 0.82,
          training_time: "2m 15s",
          model_size: "45.2 MB",
        },
        status: "failed",
        total_duration: 135000,
        started_at: "2025-01-15 10:00:00",
        completed_at: "2025-01-15 10:02:15",
        steps: [
          {
            id: "data-ingestion",
            name: "Data Ingestion",
            status: "success",
            duration: 15000,
            percentage: 11.1,
            input: {
              source: "s3://mlops-bucket/raw-data/customer_behavior_2024.csv",
              format: "CSV",
              compression: "gzip",
            },
            output: {
              records: 1250000,
              size: "2.4 GB",
              schema_validated: true,
            },
            metrics: {
              Throughput: "165 MB/s",
              "Records/sec": "83,333",
              "Memory Usage": "1.2 GB",
            },
            logs: `[10:00:00] Starting data ingestion
[10:00:01] Connecting to s3://mlops-bucket/raw-data/
[10:00:02] Found customer_behavior_2024.csv (2.4 GB)
[10:00:05] Processing chunks: 1/25
[10:00:10] Processing chunks: 15/25
[10:00:14] Processing chunks: 25/25
[10:00:15] Ingestion completed: 1,250,000 records`,
          },
          {
            id: "data-validation",
            name: "Data Validation",
            status: "success",
            duration: 13000,
            percentage: 9.6,
            input: {
              records: 1250000,
              validation_rules: 45,
              quality_threshold: 0.95,
            },
            output: {
              valid_records: 1249873,
              invalid_records: 127,
              quality_score: 0.9999,
            },
            metrics: {
              "Success Rate": "99.99%",
              "Rules Applied": "45",
              "Processing Speed": "96,154 records/sec",
            },
            logs: `[10:00:15] Starting data validation
[10:00:16] Loading 45 validation rules
[10:00:17] Schema validation: PASSED
[10:00:20] Quality checks: PASSED
[10:00:25] Outlier detection: 127 records flagged
[10:00:28] Validation completed: 99.99% success rate`,
          },
          {
            id: "feature-engineering",
            name: "Feature Engineering",
            status: "success",
            duration: 27000,
            percentage: 20.0,
            input: {
              raw_features: 23,
              transformations: ["scaling", "encoding", "interaction"],
              feature_selection: true,
            },
            output: {
              engineered_features: 156,
              selected_features: 89,
              feature_importance_calculated: true,
            },
            metrics: {
              "Features Created": "156",
              "Final Features": "89",
              "Processing Time": "27s",
            },
            logs: `[10:00:28] Starting feature engineering
[10:00:30] Creating numerical features: 45 new features
[10:00:35] Encoding categorical variables: 23 new features
[10:00:40] Generating interaction features: 88 new features
[10:00:45] Applying feature scaling and normalization
[10:00:50] Feature selection: 89 features selected
[10:00:55] Feature engineering completed`,
          },
          {
            id: "model-training",
            name: "Model Training",
            status: "success",
            duration: 45000,
            percentage: 33.3,
            input: {
              training_samples: 1000000,
              validation_samples: 250000,
              features: 89,
              algorithm: "XGBoost",
            },
            output: {
              model_trained: true,
              training_accuracy: 0.942,
              validation_accuracy: 0.918,
              model_size: "45.2 MB",
            },
            metrics: {
              "Training Accuracy": "94.2%",
              "Validation Accuracy": "91.8%",
              "Training Time": "45s",
            },
            logs: `[10:00:55] Starting XGBoost training
[10:00:56] Training set: 1,000,000 samples
[10:00:56] Validation set: 250,000 samples
[10:01:10] Epoch 100/1000 - Loss: 0.234 - Acc: 0.891
[10:01:25] Epoch 500/1000 - Loss: 0.156 - Acc: 0.925
[10:01:40] Training completed - Final accuracy: 94.2%`,
          },
          {
            id: "model-evaluation",
            name: "Model Evaluation",
            status: "failed",
            duration: 20000,
            percentage: 14.8,
            input: {
              test_samples: 250000,
              evaluation_metrics: ["accuracy", "precision", "recall", "f1"],
              threshold: 0.85,
            },
            output: {
              accuracy: 0.912,
              precision: 0.89,
              recall: 0.76,
              f1_score: 0.82,
              threshold_met: false,
            },
            metrics: {
              Accuracy: "91.2%",
              Precision: "89.0%",
              "F1-Score": "82.0%",
            },
            logs: `[10:01:40] Starting model evaluation
[10:01:41] Loading test dataset: 250,000 samples
[10:01:45] Running predictions...
[10:01:55] Calculating metrics...
[10:01:58] F1-Score: 0.82 (threshold: 0.85)
[10:02:00] ERROR: Model performance below threshold
[10:02:00] Evaluation FAILED`,
          },
          {
            id: "model-deployment",
            name: "Model Deployment",
            status: "pending",
            duration: 15000,
            percentage: 11.1,
            input: {
              deployment_target: "production",
              strategy: "blue-green",
              auto_deploy: false,
            },
            output: {
              deployment_status: "pending",
              approval_required: true,
              estimated_deployment_time: "5 minutes",
            },
            metrics: {
              Status: "Pending",
              Approval: "Required",
              "Est. Time": "5 minutes",
            },
            logs: `[10:02:00] Deployment step initiated
[10:02:00] Evaluation failed - manual approval required
[10:02:00] Deployment to production halted
[10:02:00] Awaiting manual intervention...`,
          },
        ],
      },
    };
    return executionData;
  }
}

export default ExecutionView;
