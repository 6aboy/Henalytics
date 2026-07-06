# Henalytics - Poultry Farm Management System

A comprehensive Django-based backend system for managing poultry farms with predictive analytics, inventory management, and sales tracking.

## Features

### Core Modules
1. **Flock Management** - Track multiple poultry flocks with detailed attributes
2. **Egg Production** - Daily egg collection, grading, and quality metrics
3. **Hen Performance** - Monitor health, weight, feed/water consumption
4. **Sales Management** - Track sales transactions and revenue
5. **Predictive Analytics** - ARIMA, MLR, and Hybrid forecasting models
6. **System Audit Trail** - Comprehensive logging of all operations

### Key Capabilities
- Real-time production tracking
- Forecasting with confidence intervals (95% CI)
- Role-based access control (Admin, Staff, Manager)
- RESTful API for third-party integration
- Comprehensive admin interface
- Data import from Excel
- Time series analysis and visualization

## Technology Stack

- **Framework**: Django 6.0
- **API**: Django REST Framework 3.14+
- **Database**: MySQL 5.7+
- **Machine Learning**: scikit-learn, statsmodels
- **Data Processing**: pandas, numpy
- **Frontend**: Bootstrap 5 (included in templates)

## Installation

### Prerequisites
- Python 3.8+
- MySQL 5.7+ with user credentials
- pip package manager

### Setup Steps

1. **Clone repository**
   ```bash
   git clone https://github.com/yourusername/henalytics.git
   cd henalytics
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure database**
   - Edit `henalytics/settings.py`
   - Update DATABASES configuration with your MySQL credentials:
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.mysql',
           'NAME': 'henalytics_db',
           'USER': 'your_mysql_user',
           'PASSWORD': 'your_mysql_password',
           'HOST': 'localhost',
           'PORT': '3306',
       }
   }
   ```

5. **Create database**
   ```bash
   mysql -u root -p
   CREATE DATABASE henalytics_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   EXIT;
   ```

6. **Run migrations**
   ```bash
   python manage.py makemigrations EggProduction
   python manage.py migrate
   ```

7. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

8. **Run development server**
   ```bash
   python manage.py runserver
   ```

   Access the application at `http://localhost:8000`

## API Endpoints

### Authentication
- **Base URL**: `http://localhost:8000/api/`
- **Auth Type**: Token-based (configured in Django REST Framework)

### Available Endpoints

#### Flocks
```
GET    /api/flocks/                    - List all flocks
POST   /api/flocks/                    - Create new flock
GET    /api/flocks/{id}/               - Get flock details
PUT    /api/flocks/{id}/               - Update flock
DELETE /api/flocks/{id}/               - Delete flock
GET    /api/flocks/active_flocks/      - List active flocks
GET    /api/flocks/{id}/statistics/    - Get flock statistics
```

#### Egg Production
```
GET    /api/egg-production/            - List all records
POST   /api/egg-production/            - Create production record
GET    /api/egg-production/{id}/       - Get production details
PUT    /api/egg-production/{id}/       - Update production
DELETE /api/egg-production/{id}/       - Delete production
GET    /api/egg-production/today_production/      - Today's production
GET    /api/egg-production/production_trend/      - Production trend (last N days)
POST   /api/egg-production/{id}/add_grading/      - Add egg grading
```

#### Sales
```
GET    /api/sales/                     - List sales records
POST   /api/sales/                     - Create sale
GET    /api/sales/{id}/                - Get sale details
GET    /api/sales/today_sales/         - Today's sales
GET    /api/sales/sales_summary/       - Sales summary (date range)
```

#### Hen Performance
```
GET    /api/hen-performance/           - List performance records
GET    /api/hen-performance/by_flock/  - Performance by flock
GET    /api/hen-performance/by_date_range/ - Performance by date range
```

#### Forecasts
```
GET    /api/forecasts/                 - List all forecasts
GET    /api/forecasts/by_flock/        - Forecasts for specific flock
GET    /api/forecasts/latest/          - Latest forecasts (last N days)
```

#### System Logs
```
GET    /api/system-logs/               - List system logs
GET    /api/system-logs/recent/        - Recent logs (limit N)
```

## Data Management

### Excel Data Import

Import data from Excel files using the `DataImporter` utility:

```python
from EggProduction.data_importer import DataImporter

importer = DataImporter('/path/to/data.xlsx', user=request.user)
result = importer.import_all()
```

### Excel File Structure

Required sheets in Excel file:

**Flocks Sheet**
```
flock_id | breed | initial_count | current_count | status | date_started | housing_type
FL001    | Leghorn | 1000 | 950 | active | 2024-01-01 | cage
```

**EggProduction Sheet**
```
flock_id | record_date | eggs_collected | broken_eggs | good_eggs | hen_day_production | grade_aa | grade_a
FL001    | 2024-01-15 | 850 | 10 | 825 | 89.5 | 300 | 350
```

**Sales Sheet**
```
flock_id | sale_date | eggs_sold | price_per_unit | buyer_name | status
FL001    | 2024-01-15 | 500 | 5.00 | Local Market | completed
```

**HenPerformance Sheet**
```
flock_id | record_date | average_weight | feed_consumption | mortality_count | health_status
FL001    | 2024-01-15 | 1850 | 110 | 2 | healthy
```

## Forecasting

### Generate Forecasts

Run forecasting for all active flocks:

```bash
python manage.py run_forecasts --model=hybrid --periods=7
```

### Forecast Parameters

- `--model`: Choose model type (arima, mlr, hybrid) - default: hybrid
- `--periods`: Number of days to forecast - default: 7
- `--flock-id`: Optional specific flock ID
- `--data-type`: Optional specific data type (egg_production, sales_volume, sales_price, hen_performance)

### Model Details

**ARIMA (AutoRegressive Integrated Moving Average)**
- Best for: Seasonal patterns, time series with trends
- Parameters: (p=1, d=1, q=1) - autotuned
- Output: Point forecast + 95% confidence interval

**MLR (Multiple Linear Regression)**
- Best for: Linear trends, stable patterns
- Features: Time index + lagged values
- Output: Point forecast + confidence interval based on residuals

**Hybrid Model**
- Combines ARIMA and MLR weighted by R² scores
- More robust across different data patterns
- Recommended for production use

## Admin Interface

Access Django admin at `http://localhost:8000/admin`

### Registered Models
- User Roles
- Flocks
- Hen Performance
- Egg Production
- Egg Grading
- Sales Records
- Daily Revenue
- Time Series Data
- Forecasts
- Model Performance
- System Logs

All models include:
- Search functionality
- Filtering by status/date
- Bulk actions
- Custom fieldsets for organization

## Database Schema

### Key Models

**Flock** - Master flock entity
- flock_id (unique)
- breed
- initial_count, current_count
- status (active/inactive/culled)
- date_started, date_ended
- housing_type

**EggProduction** - Daily production tracking
- flock (FK)
- record_date (unique per flock)
- eggs_collected, broken_eggs, defective_eggs, good_eggs
- hen_day_production (HDEP), hen_housed_production (HHEP)
- created_by (user attribution)

**SalesRecord** - Sales transactions
- flock (FK)
- sale_date
- eggs_sold
- price_per_unit, total_amount (auto-calculated)
- buyer_name, buyer_contact
- status (pending/completed/cancelled)

**Forecast** - Prediction results
- flock (FK)
- forecast_type
- model_type (arima/mlr/hybrid)
- forecast_date
- forecasted_value
- upper_bound, lower_bound (95% CI)
- mean_absolute_percentage_error (MAPE)
- r_squared (R²)
- model_parameters (JSON)
- is_active

## Testing

Run test suite:

```bash
python manage.py test EggProduction
```

Test coverage includes:
- Model creation and constraints
- Serializer data transformation
- API endpoint functionality
- Permission checks
- Custom action logic
- Aggregation queries

## Troubleshooting

### MySQL Connection Error
```
"Error 1045: Access denied for user 'root'@'localhost'"
```
- Verify MySQL credentials in settings.py
- Check MySQL service is running: `mysql.server start` (Mac)
- Create database if not exists

### Migration Errors
```bash
# Reset migrations (development only)
python manage.py migrate EggProduction zero
python manage.py makemigrations EggProduction
python manage.py migrate
```

### Import Errors
- Ensure all required packages are installed: `pip install -r requirements.txt`
- Verify Excel file has correct sheet names and column names

### Forecast Generation Issues
- Minimum 10 data points required for forecasting
- Check data quality (no missing values for entire days)
- Review system logs: `python manage.py shell` then query `SystemLog.objects.filter(status='error')`

## Performance Optimization

### Database Indexes
Already configured on:
- TimeSeriesData (flock, data_type, record_date)
- EggProduction unique constraint (flock, record_date)
- SalesRecord date range queries

### API Pagination
ViewSets default to 20 items per page. Configure in settings.py:
```python
REST_FRAMEWORK = {
    'PAGE_SIZE': 20,
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination'
}
```

### Forecasting Performance
- Async task execution recommended for large-scale forecasting
- Use Celery for scheduled forecast generation
- Configure in settings.py with Redis/RabbitMQ

## Deployment

### Production Checklist
1. Set `DEBUG = False` in settings.py
2. Configure `ALLOWED_HOSTS` with domain names
3. Use strong `SECRET_KEY` (generate with `django.core.management.utils.get_random_secret_key`)
4. Set up HTTPS/SSL certificates
5. Configure environment variables for sensitive data
6. Use production-grade database (configure pool, backups)
7. Set up application server (Gunicorn + Nginx)
8. Configure static files (WhiteNoise or CDN)
9. Set up logging and monitoring

### Docker Deployment

```dockerfile
FROM python:3.10
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "henalytics.wsgi:application", "--bind", "0.0.0.0:8000"]
```

## API Documentation

Interactive API documentation available at:
- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/docs/` (with redoc-js)

## License

MIT License - See LICENSE file for details

## Support

For issues and feature requests, please use the GitHub Issues tracker.

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request
