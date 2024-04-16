/* cat scripts/mongoinit.js | docker exec -i omegaml-ce_mongo_1 mongo */
db.adminCommand({
    createUser: 'admin',
    pwd : 'foobar',
    roles : ['root'],
});
