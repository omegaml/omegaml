/* cat mongoinit.js | docker exec -i omegaml_mongo_1 mongodb */
db.adminCommand({
    createUser: 'admin',
    pwd : 'jk3XVEpbpevN4BgtEbmcCpVM24gc7RVB',
    roles : ['root'],
});
