"""
Agent Executor with Automatic API Key Rotation
Wraps agent execution with retry logic for quota errors
"""
import streamlit as st
from typing import Callable, Any, Dict
from api_key_manager import get_api_key_manager, handle_api_error


def execute_agent_with_retry(
    agent_function: Callable,
    agent_name: str,
    max_retries: int = 6,
    **kwargs
) -> Dict[str, Any]:
    """
    Execute an agent with automatic API key rotation on quota errors
    
    Args:
        agent_function: The agent function to execute (e.g., run_impact_assessment)
        agent_name: Name of the agent for logging
        max_retries: Maximum number of retries (should match number of API keys)
        **kwargs: Arguments to pass to the agent function
    
    Returns:
        Agent execution result
    """
    manager = get_api_key_manager()
    
    for attempt in range(max_retries):
        try:
            # Get current API key
            api_key = manager.get_current_key()
            
            # Update kwargs with current API key
            kwargs['api_key'] = api_key
            
            # Show current attempt info
            if attempt > 0:
                st.info(f"🔄 Retry attempt {attempt + 1}/{max_retries} for {agent_name}")
            
            # Execute agent
            result = agent_function(**kwargs)
            
            # Check if result contains error
            if isinstance(result, dict) and 'error' in result:
                error_msg = result['error']
                
                # Check if it's a quota error
                if manager.is_quota_error(error_msg):
                    st.warning(f"⚠️ {agent_name}: API quota exceeded. Rotating key...")
                    new_key = manager.rotate_key(reason=f"{agent_name}_quota")
                    
                    if new_key is None:
                        st.error(f"❌ All API keys exhausted for {agent_name}")
                        return result
                    
                    # Continue to next attempt with new key
                    continue
                else:
                    # Not a quota error, return the error result
                    return result
            
            # Success!
            st.success(f"✅ {agent_name} completed successfully!")
            return result
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if it's a quota error
            if manager.is_quota_error(error_msg):
                st.warning(f"⚠️ {agent_name}: Exception - API quota exceeded. Rotating key...")
                new_key = handle_api_error(e, operation=agent_name)
                
                if new_key is None:
                    # All keys exhausted
                    return {
                        'error': f'All API keys exhausted during {agent_name}',
                        'details': error_msg
                    }
                
                # Continue to next attempt with new key
                continue
            else:
                # Not a quota error, raise it
                st.error(f"❌ {agent_name} failed: {error_msg}")
                return {
                    'error': f'{agent_name} failed',
                    'details': error_msg
                }
    
    # Max retries reached
    return {
        'error': f'{agent_name} failed after {max_retries} attempts',
        'details': 'All API keys exhausted or max retries reached'
    }


def execute_all_agents_with_retry(
    selected_asset: Dict[str, Any],
    show_progress: bool = True
) -> Dict[str, Any]:
    """
    Execute all 5 agents sequentially with automatic retry
    
    Args:
        selected_asset: The asset data to assess
        show_progress: Whether to show progress bar
    
    Returns:
        Dictionary with all agent results
    """
    from phase2_risk_resolver.agents.agent_1_cia import run_impact_assessment
    from phase2_risk_resolver.agents.agent_2_risk import run_risk_quantification
    from phase2_risk_resolver.agents.agent_3_control import run_control_discovery
    from phase2_risk_resolver.agents.agent_4_decision import run_risk_decision
    from phase2_risk_resolver.agents.agent_5_excel import run_output_generation
    
    results = {}
    
    if show_progress:
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    # Agent 1: Impact Assessment
    if show_progress:
        status_text.text("🤖 Running Agent 1: Impact Assessment...")
        progress_bar.progress(0.1)
    
    results['agent_1'] = execute_agent_with_retry(
        run_impact_assessment,
        "Agent 1: Impact Assessment",
        asset_data=selected_asset
    )
    
    if 'error' in results['agent_1']:
        st.error(f"❌ Agent 1 failed: {results['agent_1']['error']}")
        return results
    
    if show_progress:
        progress_bar.progress(0.2)
    
    # Agent 2: Risk Quantification
    if show_progress:
        status_text.text("🤖 Running Agent 2: Risk Quantification...")
        progress_bar.progress(0.3)
    
    results['agent_2'] = execute_agent_with_retry(
        run_risk_quantification,
        "Agent 2: Risk Quantification",
        asset_data=selected_asset,
        impact_results=results['agent_1']
    )
    
    if 'error' in results['agent_2']:
        st.error(f"❌ Agent 2 failed: {results['agent_2']['error']}")
        return results
    
    if show_progress:
        progress_bar.progress(0.5)
    
    # Agent 3: Control Discovery
    if show_progress:
        status_text.text("🤖 Running Agent 3: Control Discovery...")
        progress_bar.progress(0.6)
    
    results['agent_3'] = execute_agent_with_retry(
        run_control_discovery,
        "Agent 3: Control Discovery",
        asset_data=selected_asset,
        impact_results=results['agent_1'],
        risk_results=results['agent_2']
    )
    
    if 'error' in results['agent_3']:
        st.error(f"❌ Agent 3 failed: {results['agent_3']['error']}")
        return results
    
    if show_progress:
        progress_bar.progress(0.75)
    
    # Agent 4: Risk Decision
    if show_progress:
        status_text.text("🤖 Running Agent 4: Risk Decision...")
        progress_bar.progress(0.8)
    
    results['agent_4'] = execute_agent_with_retry(
        run_risk_decision,
        "Agent 4: Risk Decision",
        asset_data=selected_asset,
        impact_results=results['agent_1'],
        risk_results=results['agent_2'],
        control_results=results['agent_3']
    )
    
    if 'error' in results['agent_4']:
        st.error(f"❌ Agent 4 failed: {results['agent_4']['error']}")
        return results
    
    if show_progress:
        progress_bar.progress(0.9)
    
    # Agent 5: Output Generation
    if show_progress:
        status_text.text("🤖 Running Agent 5: Output Generation...")
        progress_bar.progress(0.95)
    
    all_results = {
        'asset_data': selected_asset,
        'agent_1': results['agent_1'],
        'agent_2': results['agent_2'],
        'agent_3': results['agent_3'],
        'agent_4': results['agent_4']
    }
    
    results['agent_5'] = execute_agent_with_retry(
        run_output_generation,
        "Agent 5: Output Generation",
        all_results=all_results
    )
    
    if show_progress:
        progress_bar.progress(1.0)
        status_text.text("✅ All agents completed!")
    
    return results
