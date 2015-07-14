module.exports = (grunt) ->
	# Project configuration.
	grunt.initConfig
		pkg: grunt.file.readJSON('package.json'),
		coffee:
			app:
				expand: true
				cwd: '.'
				src: ['**/*.coffee']
				dest: '.'
				ext: '.js'

	# These plugins provide necessary tasks.
	grunt.loadNpmTasks 'grunt-contrib-coffee'
	
	# Default task.
	grunt.registerTask 'default', ['coffee']
