#!/bin/sh

# Récupérer le nom du conteneur
TASK_NAME=$(docker inspect --format '{{ index .Config.Labels "com.docker.swarm.task.name" }}' $(hostname))

# Extraire l'index du réplica depuis le nom de la tâche (e.g., "claxon_controller_node.1.abjjpnsw04say3xfwgburg89p")
REPLICA_INDEX=$(echo $TASK_NAME | cut -d'.' -f2)
ZONE=$REPLICA_INDEX
export REPLICA_INDEX
export ZONE

IP_ADDRESS=$(docker inspect --format '{{ .NetworkSettings.Networks.backstack_network.IPAddress }}' $(hostname))
EXTERNAL_PERSONNAL_BROKER_HOST=$IP_ADDRESS
export IP_ADDRESS
export EXTERNAL_PERSONNAL_BROKER_HOST

echo "Je suis le réplica numéro: $REPLICA_INDEX"
echo "Je suis dans la zone: $ZONE"

supervisord -c /etc/supervisor/conf.d/supervisord.conf