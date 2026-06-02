# Fonction OpenFaaS Meteo

## 1) Prerequis

- OpenFaaS en marche
- `faas-cli` installe
- Docker connecte a votre registry

## 2) Configurer les secrets

```bash
echo -n "$OPENWEATHER_API_KEY" | faas-cli secret create openweather-api-key
```

Optionnel (envoi vers Discord):

```bash
echo -n "$DISCORD_WEBHOOK_URL" | faas-cli secret create discord-webhook-url
```

## 3) Mettre image Docker

Dans `stack.yml`, remplacez:

`your-dockerhub-user/meteo:latest`

par votre image (ex: `vadimdev/meteo:0.1.0`).

## 4) Build / Push / Deploy

```bash
faas-cli build -f stack.yml
faas-cli push -f stack.yml
faas-cli deploy -f stack.yml
```

## 5) Teste

```bash
echo "city=Montreal&units=metric&lang=fr" | faas-cli invoke meteo
```

La fonction lit:
- le secret OpenFaaS `openweather-api-key` (prioritaire)
- sinon la variable `OPENWEATHER_API_KEY`

Pour Discord (optionnel):
- le secret OpenFaaS `discord-webhook-url` (prioritaire)
- sinon la variable `DISCORD_WEBHOOK_URL`

Si le webhook est configure, la fonction poste aussi la meteo dans ton channel Discord.
