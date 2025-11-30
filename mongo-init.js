// This file is used by the mongo-init service in docker-compose.yml
// It is mounted but the command is executed inline in docker-compose for simplicity in this setup.
// Keeping this file as a placeholder if we want to move the logic here later.
// The logic is currently:
// try { rs.status() } catch (err) { rs.initiate({_id: "rs0", members: [{_id: 0, host: "mongo:27017"}]}) }
