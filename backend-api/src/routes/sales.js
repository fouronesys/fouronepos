const express = require('express');
const { body, validationResult } = require('express-validator');
const { query, transaction } = require('../config/database');
const { authorize } = require('../middleware/auth');

const router = express.Router();

// Get all sales
router.get('/', async (req, res) => {
  try {
    const { page = 1, limit = 50, status, date_from, date_to } = req.query;
    const offset = (page - 1) * limit;

    let whereConditions = [];
    let params = [];
    let paramCount = 0;

    if (status) {
      whereConditions.push(`status = $${++paramCount}`);
      params.push(status);
    }

    if (date_from) {
      whereConditions.push(`created_at >= $${++paramCount}`);
      params.push(date_from);
    }

    if (date_to) {
      whereConditions.push(`created_at <= $${++paramCount}`);
      params.push(date_to);
    }

    const whereClause = whereConditions.length > 0 ? `WHERE ${whereConditions.join(' AND ')}` : '';

    const salesQuery = `
      SELECT 
        s.id, s.subtotal, s.tax, s.total, s.payment_method,
        s.cash_received, s.change_amount, s.customer_name, s.customer_rnc,
        s.status, s.table_id, s.table_number, s.user_id, s.created_at,
        u.name as user_name, u.role as user_role
      FROM sales s
      LEFT JOIN users u ON s.user_id = u.id
      ${whereClause}
      ORDER BY s.created_at DESC
      LIMIT $${++paramCount} OFFSET $${++paramCount}
    `;

    params.push(limit, offset);

    const result = await query(salesQuery, params);

    // Get total count
    const countQuery = `
      SELECT COUNT(*) as total
      FROM sales s
      ${whereClause}
    `;

    const countResult = await query(countQuery, params.slice(0, -2)); // Remove limit and offset

    res.json({
      success: true,
      data: result.rows,
      pagination: {
        page: parseInt(page),
        limit: parseInt(limit),
        total: parseInt(countResult.rows[0].total),
        totalPages: Math.ceil(countResult.rows[0].total / limit)
      }
    });

  } catch (error) {
    console.error('Get sales error:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch sales'
    });
  }
});

// Get sale by ID
router.get('/:id', async (req, res) => {
  try {
    const { id } = req.params;

    const saleQuery = `
      SELECT 
        s.*, u.name as user_name, u.role as user_role
      FROM sales s
      LEFT JOIN users u ON s.user_id = u.id
      WHERE s.id = $1
    `;

    const saleResult = await query(saleQuery, [id]);

    if (saleResult.rows.length === 0) {
      return res.status(404).json({
        success: false,
        error: 'Sale not found'
      });
    }

    // Get sale items
    const itemsQuery = `
      SELECT * FROM sale_items WHERE sale_id = $1 ORDER BY id
    `;

    const itemsResult = await query(itemsQuery, [id]);

    const sale = {
      ...saleResult.rows[0],
      items: itemsResult.rows
    };

    res.json({
      success: true,
      data: sale
    });

  } catch (error) {
    console.error('Get sale error:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch sale'
    });
  }
});

// Create new sale
router.post('/', [
  body('items').isArray({ min: 1 }).withMessage('Items array is required'),
  body('subtotal').isNumeric().withMessage('Subtotal must be numeric'),
  body('tax').isNumeric().withMessage('Tax must be numeric'),
  body('total').isNumeric().withMessage('Total must be numeric'),
  body('payment_method').isIn(['cash', 'card', 'transfer']).withMessage('Valid payment method required')
], async (req, res) => {
  try {
    // Check validation errors
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        success: false,
        error: 'Validation failed',
        details: errors.array()
      });
    }

    const {
      items,
      subtotal,
      tax,
      total,
      payment_method,
      cash_received,
      change_amount,
      customer_name,
      customer_rnc,
      table_id,
      table_number,
      status = 'completed'
    } = req.body;

    const result = await transaction(async (client) => {
      // Create sale
      const saleQuery = `
        INSERT INTO sales (
          subtotal, tax, total, payment_method, cash_received, change_amount,
          customer_name, customer_rnc, table_id, table_number, status,
          user_id, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
        RETURNING *
      `;

      const saleResult = await client.query(saleQuery, [
        subtotal, tax, total, payment_method, cash_received || null, change_amount || null,
        customer_name || null, customer_rnc || null, table_id || null, table_number || null,
        status, req.user.id
      ]);

      const sale = saleResult.rows[0];

      // Create sale items
      const saleItems = [];
      for (const item of items) {
        const itemQuery = `
          INSERT INTO sale_items (
            sale_id, product_id, product_name, quantity, unit_price, total_price,
            status, created_at
          ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
          RETURNING *
        `;

        const itemResult = await client.query(itemQuery, [
          sale.id,
          item.product_id,
          item.product_name,
          item.quantity,
          item.unit_price,
          item.total_price,
          item.status || 'completed'
        ]);

        saleItems.push(itemResult.rows[0]);
      }

      return {
        ...sale,
        items: saleItems
      };
    });

    res.status(201).json({
      success: true,
      message: 'Sale created successfully',
      data: result
    });

  } catch (error) {
    console.error('Create sale error:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to create sale'
    });
  }
});

// Update sale status
router.put('/:id/status', [
  body('status').isIn(['pending', 'in_preparation', 'ready', 'served', 'completed', 'cancelled'])
    .withMessage('Valid status required')
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({
        success: false,
        error: 'Validation failed',
        details: errors.array()
      });
    }

    const { id } = req.params;
    const { status } = req.body;

    const result = await query(
      'UPDATE sales SET status = $1, updated_at = NOW() WHERE id = $2 RETURNING *',
      [status, id]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({
        success: false,
        error: 'Sale not found'
      });
    }

    res.json({
      success: true,
      message: 'Sale status updated',
      data: result.rows[0]
    });

  } catch (error) {
    console.error('Update sale status error:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to update sale status'
    });
  }
});

// Get cash summary for today
router.get('/reports/cash-summary', authorize(['ADMINISTRADOR', 'GERENTE']), async (req, res) => {
  try {
    const today = new Date().toISOString().split('T')[0];

    const summaryQuery = `
      SELECT 
        payment_method,
        COUNT(*) as transaction_count,
        SUM(total) as total_amount,
        SUM(cash_received) as total_cash_received,
        SUM(change_amount) as total_change_given
      FROM sales 
      WHERE DATE(created_at) = $1 AND status = 'completed'
      GROUP BY payment_method
      ORDER BY payment_method
    `;

    const result = await query(summaryQuery, [today]);

    // Get overall totals
    const totalQuery = `
      SELECT 
        COUNT(*) as total_transactions,
        SUM(total) as total_revenue
      FROM sales 
      WHERE DATE(created_at) = $1 AND status = 'completed'
    `;

    const totalResult = await query(totalQuery, [today]);

    res.json({
      success: true,
      data: {
        date: today,
        by_payment_method: result.rows,
        totals: totalResult.rows[0]
      }
    });

  } catch (error) {
    console.error('Cash summary error:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to generate cash summary'
    });
  }
});

module.exports = router;