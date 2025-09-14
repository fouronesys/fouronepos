const errorHandler = (err, req, res, next) => {
  console.error('Error:', err);

  // Default error
  let error = {
    status: 500,
    message: 'Internal Server Error'
  };

  // Validation errors
  if (err.name === 'ValidationError') {
    error.status = 400;
    error.message = 'Validation Error';
    error.details = err.details;
  }

  // JWT errors
  if (err.name === 'JsonWebTokenError') {
    error.status = 401;
    error.message = 'Invalid token';
  }

  if (err.name === 'TokenExpiredError') {
    error.status = 401;
    error.message = 'Token expired';
  }

  // Database errors
  if (err.code) {
    switch (err.code) {
      case '23505': // unique_violation
        error.status = 400;
        error.message = 'Duplicate entry';
        break;
      case '23503': // foreign_key_violation
        error.status = 400;
        error.message = 'Referenced record does not exist';
        break;
      case '23514': // check_violation
        error.status = 400;
        error.message = 'Invalid data format';
        break;
      default:
        error.status = 500;
        error.message = 'Database error';
    }
  }

  // Custom errors
  if (err.status) {
    error.status = err.status;
    error.message = err.message;
  }

  res.status(error.status).json({
    error: error.message,
    ...(error.details && { details: error.details }),
    ...(process.env.NODE_ENV === 'development' && { stack: err.stack })
  });
};

module.exports = {
  errorHandler
};