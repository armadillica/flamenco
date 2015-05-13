module.exports = function(grunt) {
    grunt.initConfig({
        pkg: grunt.file.readJSON('package.json'),

        jade: {
          compile: {
            options: {
              data: {
                debug: false
              },
              pretty: true,
            },
            files: [{
              expand: true,
              cwd: 'src/jade',
              src: [ '**/*.jade' ],
              dest: 'application/templates',
              ext: '.html'
            }]
          }
        },

        sass: {
            dist: {
                options: {
                    style: 'compressed'
                },
                files: {
                    'application/static/css/main.css': 'src/sass/main.sass'
                }
            }
        },

        autoprefixer: {
            no_dest: { src: 'application/static/css/main.css' }
        },

        watch: {
            files: ['src/sass/main.sass'],
            tasks: ['sass', 'autoprefixer'],
            jade: {
              files: 'src/jade/**/*.jade',
              tasks: [ 'jade' ]
            },
        }
    });

    grunt.loadNpmTasks('grunt-contrib-sass');
    grunt.loadNpmTasks('grunt-contrib-watch');
    grunt.loadNpmTasks('grunt-autoprefixer');
    grunt.loadNpmTasks('grunt-contrib-jade');

    grunt.registerTask('default', ['sass', 'autoprefixer', 'jade']);
};
