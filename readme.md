docker build -t fpds-server .

docker run -d -p 8082:8082 --name fpds-server-test fpds-server

```commandline

copy image 
gcloud builds submit --region=us-east1 --config cloudbuild.yaml
create secret
gcloud config set project cloudmatos-saas-demo

gcloud secrets create nginx_config_fpds --replication-policy="automatic" --data-file="./nginx.conf"

export PROJECT_ID=$(gcloud config get-value project)
export PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
    --role="roles/artifactregistry.writer"
    
gcloud secrets add-iam-policy-binding nginx_config_fpds \
	--member=serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com \
	--role='roles/secretmanager.secretAccessor'

gcloud run services replace service_ingress.yaml
gcloud secrets list --project $PROJECT_ID
gcloud run services delete demo-srv-nginx-ingress --region us-central1
gcloud secrets delete nginx_config_external_api_prod
```