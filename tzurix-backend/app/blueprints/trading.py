"""
Trading Blueprint
Buy/sell endpoints for agent tokens.
"""

from flask import Blueprint, jsonify, request

from app.services.trading import TradingService

trading_bp = Blueprint('trading', __name__, url_prefix='/api/trade')


@trading_bp.route('/quote', methods=['GET'])
def get_trade_quote():
    """Get a price quote for buying or selling."""
    agent_id = request.args.get('agent_id', type=int)
    side = request.args.get('side', 'buy')
    amount = request.args.get('amount', type=float)
    
    if not agent_id or not amount:
        return jsonify({
            'success': False,
            'error': 'Missing agent_id or amount'
        }), 400
    
    result = TradingService.get_quote(agent_id, side, amount)
    
    if not result.get('success'):
        return jsonify(result), 404 if 'not found' in result.get('error', '') else 400
    
    return jsonify(result)


@trading_bp.route('/buy', methods=['POST'])
def buy_tokens():
    """Buy agent tokens."""
    data = request.get_json()
    
    agent_id = data.get('agent_id')
    trader_wallet = data.get('trader_wallet')
    sol_amount = data.get('sol_amount', 0)
    tx_signature = data.get('tx_signature')
    
    if not agent_id or not trader_wallet or sol_amount <= 0:
        return jsonify({
            'success': False,
            'error': 'Missing required fields: agent_id, trader_wallet, sol_amount'
        }), 400
    
    result = TradingService.execute_buy(agent_id, trader_wallet, sol_amount, tx_signature)
    
    if not result.success:
        return jsonify({'success': False, 'error': result.error}), 400
    
    return jsonify({
        'success': True,
        'message': 'Purchase successful',
        'trade': TradingService.trade_to_dict(result.trade),
        'holding': TradingService.holding_to_dict(result.holding),
        'sol_spent': sol_amount,
        'fee_sol': sol_amount * 0.01
    })


@trading_bp.route('/sell', methods=['POST'])
def sell_tokens():
    """Sell agent tokens back to the protocol."""
    data = request.get_json()
    
    agent_id = data.get('agent_id')
    trader_wallet = data.get('trader_wallet')
    token_amount = data.get('token_amount', 0)
    tx_signature = data.get('tx_signature')
    
    if not agent_id or not trader_wallet or token_amount <= 0:
        return jsonify({
            'success': False,
            'error': 'Missing required fields: agent_id, trader_wallet, token_amount'
        }), 400
    
    result = TradingService.execute_sell(agent_id, trader_wallet, token_amount, tx_signature)
    
    if not result.success:
        status_code = 400
        if 'not found' in result.error.lower():
            status_code = 404
        return jsonify({'success': False, 'error': result.error}), status_code
    
    from app.services.pricing import PricingService
    from app.models import Agent
    agent = Agent.query.get(agent_id)
    price_data = PricingService.calculate_price(agent.current_score)
    sol_before_fee = token_amount * price_data.price_sol
    sol_received = sol_before_fee * 0.99
    
    return jsonify({
        'success': True,
        'message': 'Sale successful',
        'trade': TradingService.trade_to_dict(result.trade),
        'sol_received': sol_received,
        'fee_sol': sol_before_fee * 0.01
    })
