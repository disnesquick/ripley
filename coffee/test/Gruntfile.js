(function() {
  module.exports = function(grunt) {
    grunt.initConfig({
      pkg: grunt.file.readJSON('package.json'),
      coffee: {
        app: {
          expand: true,
          cwd: '.',
          src: ['**/*.coffee'],
          dest: '.',
          ext: '.js'
        }
      }
    });
    grunt.loadNpmTasks('grunt-contrib-coffee');
    return grunt.registerTask('default', ['coffee']);
  };

}).call(this);
