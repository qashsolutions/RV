"""
Export trained models to ONNX format for browser-side inference.
"""

import os
import json
import argparse
import numpy as np
import joblib

from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
import onnx

from features import get_feature_columns


def export_model_to_onnx(model, model_name: str, n_features: int, output_dir: str):
    """Export a single sklearn-compatible model to ONNX."""
    os.makedirs(output_dir, exist_ok=True)

    initial_type = [('float_input', FloatTensorType([None, n_features]))]

    try:
        onnx_model = convert_sklearn(model, initial_types=initial_type,
                                     target_opset=15)
        output_path = os.path.join(output_dir, f'{model_name}.onnx')
        onnx.save_model(onnx_model, output_path)

        # Check file size
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"Exported {model_name} to ONNX: {output_path} ({size_mb:.2f} MB)")
        return output_path

    except Exception as e:
        print(f"Warning: Could not export {model_name} to ONNX: {e}")
        print(f"This model will use JSON weight export as fallback.")
        return export_model_to_json(model, model_name, output_dir)


def export_model_to_json(model, model_name: str, output_dir: str):
    """Fallback: export model weights as JSON for JS reconstruction."""
    os.makedirs(output_dir, exist_ok=True)

    if hasattr(model, 'get_booster'):
        # XGBoost
        json_path = os.path.join(output_dir, f'{model_name}.json')
        model.get_booster().save_model(json_path)
        print(f"Exported {model_name} as JSON: {json_path}")
        return json_path

    if hasattr(model, 'booster_'):
        # LightGBM
        json_path = os.path.join(output_dir, f'{model_name}.txt')
        model.booster_.save_model(json_path)
        print(f"Exported {model_name} as LightGBM text: {json_path}")
        return json_path

    # Generic: serialize tree structure
    if hasattr(model, 'tree_'):
        tree_data = {
            'feature': model.tree_.feature.tolist(),
            'threshold': model.tree_.threshold.tolist(),
            'children_left': model.tree_.children_left.tolist(),
            'children_right': model.tree_.children_right.tolist(),
            'value': model.tree_.value.flatten().tolist(),
            'n_features': model.n_features_in_,
        }
        json_path = os.path.join(output_dir, f'{model_name}_tree.json')
        with open(json_path, 'w') as f:
            json.dump(tree_data, f)
        print(f"Exported {model_name} tree structure: {json_path}")
        return json_path

    print(f"Warning: Cannot export {model_name} — unsupported model type")
    return None


def export_all(model_dir: str, output_dir: str):
    """Export all trained models from a directory."""
    os.makedirs(output_dir, exist_ok=True)

    feature_cols = get_feature_columns()
    n_features = len(feature_cols)

    # Load ensemble config
    config_path = os.path.join(model_dir, 'ensemble_config.json')
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
    else:
        config = {}

    exported = {}
    for model_file in sorted(os.listdir(model_dir)):
        if model_file.endswith('.joblib'):
            model_name = model_file.replace('_model.joblib', '')
            model = joblib.load(os.path.join(model_dir, model_file))
            path = export_model_to_onnx(model, model_name, n_features, output_dir)
            if path:
                exported[model_name] = os.path.basename(path)

    # Save manifest for frontend
    manifest = {
        'models': exported,
        'feature_columns': feature_cols,
        'weights': config.get('weights', {}),
        'metrics': config.get('ensemble_metrics', {}),
    }
    manifest_path = os.path.join(output_dir, 'model_manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f"\nModel manifest saved to {manifest_path}")


def main():
    parser = argparse.ArgumentParser(description='Export models to ONNX')
    parser.add_argument('--model-dir', default='./trained_models',
                        help='Directory containing trained .joblib models')
    parser.add_argument('--output', default='../frontend/public/models',
                        help='Output directory for ONNX files')
    args = parser.parse_args()

    export_all(args.model_dir, args.output)


if __name__ == '__main__':
    main()
