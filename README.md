# Fonction OpenFaaS Meteo

Cette fonction recupere la meteo actuelle via l'API OpenWeather.

## 1) Prerequis

- OpenFaaS en marche
- `faas-cli` installe
- Docker connecte a votre registry

## 2) Configurer la cle API (secret OpenFaaS)

```bash
echo -n "$OPENWEATHER_API_KEY" | faas-cli secret create openweather-api-key
```

## 3) Mettre votre image Docker

Dans `stack.yml`, remplacez:

`your-dockerhub-user/meteo:latest`

par votre image (ex: `vadimdev/meteo:0.1.0`).

## 4) Build / Push / Deploy

```bash
faas-cli build -f stack.yml
faas-cli push -f stack.yml
faas-cli deploy -f stack.yml
```

## 5) Tester

```bash
echo "city=Montreal&units=metric&lang=fr" | faas-cli invoke meteo
```

La fonction lit:
- le secret OpenFaaS `openweather-api-key` (prioritaire)
- sinon la variable `OPENWEATHER_API_KEY`
