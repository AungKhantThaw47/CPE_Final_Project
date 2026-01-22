import mlflow
import numpy as np
import os
from sklearn.linear_model import LogisticRegression
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score
import matplotlib.pyplot as plt

# Set GCP project for artifact storage
os.environ["GOOGLE_CLOUD_PROJECT"] = "cpe-final-project"

# Set MLflow tracking URI to your deployed server
mlflow.set_tracking_uri("https://mlflow-server-7y5bfe32jq-as.a.run.app")

# Create or get experiment
experiment_name = "test-experiment"
try:
    experiment_id = mlflow.create_experiment(experiment_name)
except:
    experiment_id = mlflow.get_experiment_by_name(experiment_name).experiment_id

mlflow.set_experiment(experiment_name)

# Generate sample dataset
print("Generating sample dataset...")
X, y = make_classification(
    n_samples=1000,
    n_features=20,
    n_informative=15,
    n_redundant=5,
    random_state=42
)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Start MLflow run
with mlflow.start_run(run_name="logistic-regression-test"):
    print("Training model...")
    
    # Hyperparameters
    C = 1.0
    max_iter = 100
    solver = "lbfgs"
    
    # Log parameters
    mlflow.log_param("C", C)
    mlflow.log_param("max_iter", max_iter)
    mlflow.log_param("solver", solver)
    mlflow.log_param("n_samples", len(X_train))
    mlflow.log_param("n_features", X_train.shape[1])
    
    # Train model
    model = LogisticRegression(C=C, max_iter=max_iter, solver=solver, random_state=42)
    model.fit(X_train, y_train)
    
    # Make predictions
    y_pred = model.predict(X_test)
    
    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    
    # Log metrics
    mlflow.log_metric("accuracy", accuracy)
    mlflow.log_metric("f1_score", f1)
    
    print(f"Accuracy: {accuracy:.4f}")
    print(f"F1 Score: {f1:.4f}")
    
    # Create a simple confusion matrix plot
    from sklearn.metrics import confusion_matrix
    
    cm = confusion_matrix(y_test, y_pred)
    plt.figure(figsize=(8, 6))
    plt.imshow(cm, interpolation='nearest', cmap='Blues')
    plt.title('Confusion Matrix')
    plt.colorbar()
    
    # Add text annotations
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            plt.text(j, i, str(cm[i, j]), ha='center', va='center', color='white' if cm[i, j] > cm.max()/2 else 'black')
    
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.tight_layout()
    plt.savefig("confusion_matrix.png")
    plt.close()
    
    # Log the plot as an artifact
    mlflow.log_artifact("confusion_matrix.png")
    
    # Log the model (use artifact_path parameter for compatibility)
    mlflow.sklearn.log_model(model, artifact_path="model")
    
    # Get the run ID
    run_id = mlflow.active_run().info.run_id
    print(f"\n✅ Run logged successfully!")
    print(f"Run ID: {run_id}")
    print(f"View in MLflow UI: https://mlflow-server-7y5bfe32jq-as.a.run.app/#/experiments/{experiment_id}/runs/{run_id}")

print("\n🎉 MLflow test completed successfully!")
