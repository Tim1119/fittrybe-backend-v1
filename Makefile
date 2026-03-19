.PHONY: run test migrate shell worker beat coverage lint docker-up docker-down superuser logs

run:
	python manage.py runserver

test:
	venv/bin/pytest apps/ tests/ -v --tb=short

migrate:
	python manage.py makemigrations
	python manage.py migrate

shell:
	python manage.py shell_plus

worker:
	celery -A fittrybe_backend worker --loglevel=info

beat:
	celery -A fittrybe_backend beat --loglevel=info

coverage:
	venv/bin/pytest apps/ tests/ --cov=apps --cov-report=html --cov-report=term-missing

lint:
	venv/bin/black apps/ tests/
	venv/bin/isort apps/ tests/
	venv/bin/flake8 apps/ tests/

docker-up:
	docker-compose up -d db redis

docker-down:
	docker-compose down

superuser:
	python manage.py createsuperuser

logs:
	docker-compose logs -f
