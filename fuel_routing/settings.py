"""
Django settings for fuel_routing project.
"""

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-fuel-routing-assessment-key-for-matias-spotter'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'rest_framework',
    'corsheaders',
    # Local apps
    'routing_api.apps.RoutingApiConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'fuel_routing.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'fuel_routing.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
}

# CORS configuration
CORS_ALLOW_ALL_ORIGINS = True

# Fuel and Routing Configuration
FUEL_STOPS_CSV_PATH = BASE_DIR / 'data' / 'fuel_stops_geocoded.csv'
OSRM_BASE_URL = 'http://router.project-osrm.org'
NOMINATIM_BASE_URL = 'https://nominatim.openstreetmap.org'

# Vehicle parameters as specified in assessment
VEHICLE_MAX_RANGE_MILES = 500.0
VEHICLE_MPG = 10.0
DEFAULT_CORRIDOR_RADIUS_MILES = 10.0

# Continental USA bounding box for validation
USA_BOUNDING_BOX = {
    'min_lat': 24.396308,   # Southernmost point in continental US (Key West area)
    'max_lat': 49.384358,   # Northernmost point (Northwest Angle, MN)
    'min_lon': -125.000000, # Westernmost point (Cape Alava, WA)
    'max_lon': -66.934570,  # Easternmost point (West Quoddy Head, ME)
    # Alaska & Hawaii bounds for broader support if needed
    'ak_bounds': {'min_lat': 51.0, 'max_lat': 72.0, 'min_lon': -180.0, 'max_lon': -129.0},
    'hi_bounds': {'min_lat': 18.0, 'max_lat': 23.0, 'min_lon': -161.0, 'max_lon': -154.0},
}
