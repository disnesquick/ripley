module.exports = (grunt) ->
	# Project configuration.
	grunt.initConfig
		pkg: grunt.file.readJSON('package.json'),
		coffee:
			app:
				expand: true
				cwd: 'src'
				src: ['**/*.coffee']
				dest: 'build/raw'
				ext: '.js'
			options:
				bare: true
		
		uglify:
			build:
				expand: true
				cwd: 'build/'
				src: ['<%= pkg.name %>.js']
				dest: 'build/'
				ext: '.min.js'
		
		clean:
			js: ['build/raw/*.js','build/min/*.js']
		
		watch:
			app:
				files: '**/*.coffee'
				tasks: ['coffee', 'uglify']
		
		concat_in_order:
			build:
				files:
					'build/<%= pkg.name %>.js' : ['build/raw/**/*.js']
				
				options:
					extractRequired : (filePath, fileContent) ->
						@getMatches /@require\s(.*)/g, fileContent
					
					extractDeclared : (filePath, fileContent) ->
						@getMatches /@declare\s(.*)/g, fileContent
	
	# These plugins provide necessary tasks.
	grunt.loadNpmTasks 'grunt-contrib-coffee'
	grunt.loadNpmTasks 'grunt-contrib-watch'
	grunt.loadNpmTasks 'grunt-concat-in-order'
	grunt.loadNpmTasks 'grunt-contrib-uglify'
	grunt.loadNpmTasks 'grunt-contrib-clean'
	grunt.loadNpmTasks 'grunt-contrib-concat'
	
	# Default task.
	grunt.registerTask 'default', ['clean', 'coffee', 'concat_in_order', 'uglify']
