#!/usr/bin/env python3
"""
Script to fetch and display the latest OpenAI models
This helps keep the model selection up-to-date with the latest available models
"""

import os
import sys
from typing import List, Dict, Any

def fetch_openai_models() -> List[Dict[str, Any]]:
    """Fetch the latest models from OpenAI API"""
    try:
        import openai
        from openai import OpenAI
        
        # Initialize OpenAI client
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("❌ OPENAI_API_KEY not found in environment variables")
            print("Please set your OpenAI API key to fetch the latest models")
            return []
        
        client = OpenAI(api_key=api_key)
        
        # Fetch all models
        print("🔍 Fetching latest OpenAI models...")
        models = client.models.list()
        
        # Filter for relevant models (GPT family)
        gpt_models = []
        for model in models.data:
            model_id = model.id
            if any(keyword in model_id.lower() for keyword in ['gpt', 'o1']):
                gpt_models.append({
                    'id': model_id,
                    'created': model.created,
                    'owned_by': model.owned_by
                })
        
        # Sort by creation date (newest first)
        gpt_models.sort(key=lambda x: x['created'], reverse=True)
        
        return gpt_models
        
    except ImportError:
        print("❌ OpenAI library not installed. Please install it with: pip install openai")
        return []
    except Exception as e:
        print(f"❌ Error fetching models: {e}")
        return []

def categorize_models(models: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Categorize models by family"""
    categories = {
        'gpt-5': [],
        'o1': [],
        'gpt-4o': [],
        'gpt-4': [],
        'gpt-3.5': []
    }
    
    for model in models:
        model_id = model['id']
        
        if 'gpt-5' in model_id.lower():
            categories['gpt-5'].append(model_id)
        elif 'o1' in model_id.lower():
            categories['o1'].append(model_id)
        elif 'gpt-4o' in model_id.lower():
            categories['gpt-4o'].append(model_id)
        elif 'gpt-4' in model_id.lower():
            categories['gpt-4'].append(model_id)
        elif 'gpt-3.5' in model_id.lower():
            categories['gpt-3.5'].append(model_id)
    
    return categories

def print_models_report(models: List[Dict[str, Any]]):
    """Print a formatted report of available models"""
    if not models:
        print("❌ No models found")
        return
    
    print(f"\n✅ Found {len(models)} GPT/OpenAI models")
    print("=" * 60)
    
    # Categorize models
    categories = categorize_models(models)
    
    for category, model_list in categories.items():
        if model_list:
            print(f"\n🔸 {category.upper()} Family:")
            for model_id in model_list:
                print(f"  • {model_id}")
    
    print(f"\n📋 Complete model list for configuration:")
    print("=" * 60)
    
    for model in models:
        print(f"'{model['id']}',")

def generate_updated_configurations(models: List[Dict[str, Any]]):
    """Generate updated model configurations for frontend and backend"""
    if not models:
        return
    
    # Filter for the most relevant models for music generation
    relevant_models = []
    for model in models:
        model_id = model['id']
        # Include models that are likely good for creative tasks
        if any(keyword in model_id.lower() for keyword in [
            'gpt-5', 'o1', 'gpt-4o', 'gpt-4-turbo', 'gpt-4-', 'gpt-3.5-turbo'
        ]):
            # Exclude fine-tuned models and instruct variants for now
            if not any(exclude in model_id.lower() for exclude in [
                'instruct', 'code', 'davinci', 'babbage', 'ada', 'curie'
            ]):
                relevant_models.append(model_id)
    
    print(f"\n🎵 Recommended models for music generation:")
    print("=" * 60)
    
    # Sort models by preference (newest and most capable first)
    preference_order = ['gpt-5', 'o1', 'gpt-4o', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5']
    
    def model_priority(model_id):
        for i, prefix in enumerate(preference_order):
            if prefix in model_id.lower():
                return i
        return len(preference_order)
    
    relevant_models.sort(key=model_priority)
    
    print("\n// Frontend aiStore.ts models array:")
    print("models: [")
    for model_id in relevant_models:
        print(f"  '{model_id}',")
    print("]")
    
    print(f"\n// Backend model mapping (add these to _map_openai_model):")
    for model_id in relevant_models:
        print(f"'{model_id}': '{model_id}',")
    
    print(f"\n// Frontend display names (add these to modelDisplayNames):")
    for model_id in relevant_models:
        display_name = model_id.replace('-', ' ').title().replace('Gpt', 'GPT').replace('O1', 'o1')
        print(f"'{model_id}': '{display_name}',")

if __name__ == "__main__":
    print("🤖 OpenAI Model Updater")
    print("=" * 40)
    
    models = fetch_openai_models()
    print_models_report(models)
    generate_updated_configurations(models)
    
    print(f"\n💡 Next steps:")
    print("1. Update frontend/src/stores/aiStore.ts with the new models array")
    print("2. Update backend model mapping in langgraph_song_generator.py")
    print("3. Update frontend display names in components")
    print("4. Test with the new models")
