helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update


helm install postgres bitnami/postgresql \
  --namespace openfaas-fn \
  --set auth.database=openfaas_logs \
  --set auth.username=openfaas_user \
  --set auth.password=openfaas_password \
  --set primary.persistence.size=5Gi