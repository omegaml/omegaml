/* cat scripts/mongoinit.js | docker exec -i omegaml-cemongo_1 mongo */
db.adminCommand({
    createUser: 'admin',
    pwd : 'foobar',
    roles : ['root'],
});
